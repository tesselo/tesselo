import io
import operator
import tempfile
from unittest.mock import patch

import dateutil
from raster.models import RasterLayer, RasterTile
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster_aggregation.models import AggregationArea, AggregationLayer
from tests.mock_functions import patch_get_raster_tile_range_100

from classify.models import PredictedLayer
from django.contrib.auth.models import User
from django.contrib.gis.gdal import GDALRaster
from django.core.files import File
from django.test import TestCase, override_settings
from django.urls import reverse
from formulary.models import Formula, PredictedLayerFormula
from report.models import ReportAggregation, ReportAggregationLayerSrid, ReportSchedule, ReportScheduleTask
from report.tasks import push_reports
from report.utils import populate_vc
from sentinel.models import Composite, MGRSTile, SentinelTile, SentinelTileBand


class AggregationViewTestsBase(TestCase):

    def setUp(self):
        aggfile = tempfile.NamedTemporaryFile(suffix='.zip')

        self.agglayer = AggregationLayer.objects.create(
            name='Testfile',
            name_column='test',
            shapefile=File(open(aggfile.name), name='test.shp.zip')
        )

        self.aggarea = AggregationArea.objects.create(
            name='Testarea',
            aggregationlayer=self.agglayer,
            geom='SRID=3857;MULTIPOLYGON (((11843687 -458452, 11843887 -458452, 11843887 -458252, 11843687 -458252, 11843687 -458452)))',
        )
        self.aggarea2 = AggregationArea.objects.create(
            name='Testarea',
            aggregationlayer=self.agglayer,
            geom='SRID=3857;MULTIPOLYGON (((11843687 -458452, 11843887 -458452, 11843887 -458252, 11843687 -458252, 11843687 -458452)))',
        )

        self.formula = Formula.objects.create(
            name='Formula',
            formula='B2/B3',
            min_val=-100,
            max_val=100,
        )

        self.composite = Composite.objects.create(
            name='Bananastand December 2015',
            min_date='2015-12-01',
            max_date='2015-12-31',
        )

        self.predictedlayer = PredictedLayer.objects.create()

        # Set up sentineltile.
        mgrstile = MGRSTile.objects.create(utm_zone='AA', latitude_band='2', grid_square='AA',)

        self.stile = SentinelTile.objects.create(
            prefix='test',
            datastrip='test',
            product_name='test',
            mgrstile=mgrstile,
            collected=dateutil.parser.parse("2018-01-01T19:04:17.320Z"),
            cloudy_pixel_percentage=0.95,
            data_coverage_percentage=100,
        )

        SentinelTileBand.objects.create(tile=self.stile, band='B02.jp2', layer=RasterLayer.objects.create(name='b02')),
        SentinelTileBand.objects.create(tile=self.stile, band='B03.jp2', layer=RasterLayer.objects.create(name='b03')),

    def _create_report_schedule(self):
        sc = ReportSchedule.objects.create(active=True)
        sc.formulas.add(self.formula)
        sc.composites.add(self.composite)
        sc.aggregationlayers.add(self.agglayer)
        return sc


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, LOCAL=True)
@patch('report.utils.get_raster_tile', patch_get_raster_tile_range_100)
class AggregationViewTests(AggregationViewTestsBase):

    def test_create_aggregator_composite(self):
        agg = ReportAggregation(
            formula=self.formula,
            composite=self.composite,
            aggregationlayer=self.agglayer,
            aggregationarea=self.aggarea,
        )
        vc = agg.get_valuecount()
        vc = populate_vc(vc, 3857)
        agg.valuecountresult = vc
        agg.copy_valuecount()
        agg.save()
        self.assertEqual(agg.valuecountresult.formula, 'B2/B3')
        self.assertEqual(
            agg.valuecountresult.layer_names,
            {
                'B2': self.composite.compositeband_set.get(band='B02.jp2').rasterlayer_id,
                'B3': self.composite.compositeband_set.get(band='B03.jp2').rasterlayer_id,
            }
        )
        self.assertEqual(agg.valuecountresult.grouping, 'continuous')
        self.assertDictEqual(agg.value, agg.valuecountresult.value)
        self.assertEqual(agg.stats_avg, agg.valuecountresult.stats_avg)

    def test_create_aggregator_predicted(self):
        agg = ReportAggregation(
            formula=self.formula,
            predictedlayer=self.predictedlayer,
            aggregationlayer=self.agglayer,
            aggregationarea=self.aggarea,

        )
        vc = agg.get_valuecount()
        vc = populate_vc(vc, 3857)
        agg.valuecountresult = vc
        agg.copy_valuecount()
        agg.save()
        self.assertEqual(
            agg.valuecountresult.layer_names,
            {
                'x': self.predictedlayer.rasterlayer_id,
            }
        )
        self.assertEqual(agg.valuecountresult.grouping, 'discrete')
        self.assertDictEqual(agg.value, agg.valuecountresult.value)
        self.assertEqual(agg.stats_avg, agg.valuecountresult.stats_avg)

    def test_create_aggregator_predicted_formula(self):
        # Create and populated predictedlayer.
        tile_rst = GDALRaster({
            'name': '/vsimem/testtile_pred.tif',
            'driver': 'tif',
            'srid': WEB_MERCATOR_SRID,
            'width': WEB_MERCATOR_TILESIZE,
            'height': WEB_MERCATOR_TILESIZE,
            'origin': (11833687.0, -469452.0),
            'scale': (1, -1),
            'datatype': 1,
            'bands': [{'nodata_value': 0, 'data': range(WEB_MERCATOR_TILESIZE ** 2)}],
        })
        tile_rst = File(io.BytesIO(tile_rst.vsi_buffer), name='tile_pred.tif')
        RasterTile.objects.create(
            rasterlayer=self.predictedlayer.rasterlayer,
            rast=tile_rst,
            tilex=1234,
            tiley=1234,
            tilez=11,
        )
        PredictedLayerFormula.objects.create(
            formula=self.formula,
            predictedlayer=self.predictedlayer,
            key='Bananastand',
        )
        self.formula.formula = 'B3/B2+Bananastand'
        self.formula.save()
        agg = ReportAggregation(
            formula=self.formula,
            composite=self.composite,
            aggregationlayer=self.agglayer,
            aggregationarea=self.aggarea,
        )
        vc = agg.get_valuecount()
        vc = populate_vc(vc, 3857)
        agg.valuecountresult = vc
        agg.copy_valuecount()
        agg.save()
        self.assertEqual(
            agg.valuecountresult.layer_names,
            {
                'B2': self.composite.compositeband_set.get(band='B02.jp2').rasterlayer_id,
                'B3': self.composite.compositeband_set.get(band='B03.jp2').rasterlayer_id,
                'Bananastand': self.predictedlayer.rasterlayer_id,
            }
        )
        self.assertEqual(
            agg.valuecountresult.formula,
            self.formula.formula,
        )
        self.assertDictEqual(agg.value, agg.valuecountresult.value)
        self.assertEqual(agg.stats_avg, agg.valuecountresult.stats_avg)

    def test_report_schedule_formula_change(self):
        self._create_report_schedule()
        self.assertEqual(ReportAggregation.objects.count(), 0)
        self.formula.formula = 'B3/B2'
        self.formula.save()
        self.assertEqual(ReportAggregation.objects.count(), 2)

    def test_report_schedule_formula_range_change(self):
        self._create_report_schedule()
        self.assertEqual(ReportAggregation.objects.count(), 0)
        self.formula.min_val = -100
        self.formula.max_val = 1000
        self.formula.save()
        self.assertEqual(ReportAggregation.objects.count(), 2)

    def test_report_schedule_task(self):
        self._create_report_schedule()
        push_reports('composite', self.composite.id)
        # Ensure task was created and has status finished.
        task = ReportScheduleTask.objects.get(
            composite=self.composite,
            formula=self.formula,
            aggregationlayer=self.agglayer,
        )
        self.assertEqual(task.status, ReportScheduleTask.FINISHED)

    def test_report_schedule_push(self):
        self._create_report_schedule()
        push_reports('composite', self.composite.id)
        self.assertEqual(ReportAggregation.objects.count(), 2)

    def test_report_schedule_populate_reportschedule(self):
        sc = self._create_report_schedule()
        push_reports('reportschedule', sc.id)
        self.assertEqual(ReportAggregation.objects.count(), 2)

    def test_report_schedule_populate_error(self):
        sc = self._create_report_schedule()
        with self.assertRaisesMessage(ValueError, 'Failed finding reports to push.'):
            push_reports('unknown', sc.id)

    def test_report_schedule_populate_agglayer(self):
        self._create_report_schedule()
        push_reports('aggregationlayer', self.agglayer.id)
        self.assertEqual(ReportAggregation.objects.count(), 2)

    def test_report_schedule_populate_composite(self):
        self._create_report_schedule()
        push_reports('composite', self.composite.id)
        self.assertEqual(ReportAggregation.objects.count(), 2)

    def test_report_schedule_populate_composite_custom_srid(self):
        self._create_report_schedule()
        ReportAggregationLayerSrid.objects.create(aggregationlayer=self.agglayer, srid=3410)
        push_reports('composite', self.composite.id)
        self.assertEqual(ReportAggregation.objects.count(), 2)
        self.assertEqual(ReportAggregation.objects.first().srid, 3410)

    def test_report_agglayer_srid_not_meters_error(self):
        msg = 'Only meter or metre are allowed as linear units. Found "unknown".'
        with self.assertRaisesMessage(ValueError, msg):
            ReportAggregationLayerSrid.objects.create(aggregationlayer=self.agglayer, srid=4326)

    def test_report_schedule_push_processing(self):
        self._create_report_schedule()
        # Create report task tracker with status processing.
        ReportScheduleTask.objects.create(
            composite=self.composite,
            formula=self.formula,
            aggregationlayer=self.agglayer,
            status=ReportScheduleTask.PROCESSING,
        )
        push_reports('composite', self.composite.id)
        # The report was not pushed.
        self.assertEqual(ReportAggregation.objects.count(), 0)

    def test_report_counts_copy(self):
        self._create_report_schedule()
        push_reports('composite', self.composite.id)
        agg = ReportAggregation.objects.first()
        # Statistics have been computed and are not null.
        self.assertIsNotNone(agg.stats_max)
        self.assertTrue(agg.stats_max > 0)
        # Values have been copied correctly from valuecounts to aggreports.
        self.assertEqual(agg.stats_min, agg.valuecountresult.stats_min)
        self.assertDictEqual(agg.value, agg.valuecountresult.value)
        # Percentages have been calculated.
        key = next(iter(agg.value))
        valsum = sum([float(val) for key, val in agg.value.items()])
        self.assertEqual(float(agg.value_percentage[key]), round(float(agg.value[key]) / valsum, 7))

    def test_percentage_covered(self):
        # Prepare data.
        ReportAggregation.objects.all().delete()
        AggregationArea.objects.all().delete()
        self.aggarea = AggregationArea.objects.create(
            name='Testarea',
            aggregationlayer=self.agglayer,
            geom='SRID=3857;MultiPolygon(((-956855.41533996479120106 4889371.11169220320880413, -935733.89684526750352234 4890864.55239384807646275, -934453.80481528583914042 4901105.28863370139151812, -938507.42957689450122416 4911772.7222168818116188, -950028.25784672936424613 4918599.87971011735498905, -960055.64541491901036352 4917959.83369512669742107, -965816.0595498364418745 4906012.30808196403086185, -958775.5533849373459816 4903665.4726936649531126, -949388.21183173847384751 4908572.49214192759245634, -945334.58707012992817909 4909852.5841719089075923, -939574.1729352124966681 4904305.51870865561068058, -940640.91629353049211204 4897691.70988708361983299, -947254.72511510236654431 4895984.92051377426832914, -954935.27729499235283583 4895558.22317044716328382, -956855.41533996479120106 4889371.11169220320880413)))'
        )
        # Compute statistics.
        self._create_report_schedule()
        push_reports('composite', self.composite.id)
        # Percentage cover is close to one (given a pixel resolution error).
        agg = ReportAggregation.objects.first()
        self.assertAlmostEqual(agg.stats_percentage_covered, 1.000012866577283)

    def test_percentage_covered_zero(self):
        # Push formula bounds out of range.
        self.formula.min_val = -1000
        self.formula.max_val = -999
        self.formula.save()
        # Compute aggregation.
        self._create_report_schedule()
        push_reports('composite', self.composite.id)
        # All values are out of range, zero pecent was covered by agg.
        agg = ReportAggregation.objects.first()
        self.assertEqual(agg.stats_percentage_covered, 0)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, LOCAL=True)
@patch('report.utils.get_raster_tile', patch_get_raster_tile_range_100)
class AggregationViewTestsApi(AggregationViewTestsBase):

    def setUp(self):

        super().setUp()

        self.usr = User.objects.create_superuser(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )
        self.client.login(username='michael', password='bananastand')

    def test_api_ordering(self):
        # Prepare data.
        ReportAggregation.objects.all().delete()
        for i in range(5):
            aggarea = AggregationArea.objects.create(
                name='Testarea {}'.format(i),
                aggregationlayer=self.agglayer,
                geom='SRID=3857;MULTIPOLYGON (((11843687 -458452, 11843887 -458452, 11843887 -458252, 11843687 -458252, 11843687 -458452)))',
            )
            agg = ReportAggregation(
                formula=self.formula,
                predictedlayer=self.predictedlayer,
                aggregationlayer=self.agglayer,
                aggregationarea=aggarea,

            )
            vc = agg.get_valuecount()
            vc = populate_vc(vc, 3857)
            agg.valuecountresult = vc
            agg.copy_valuecount()
            agg.save()

        # Prepare url.
        url = reverse('reportaggregation-list')
        url += '?aggregationlayer={}'.format(self.agglayer.id)

        # Prepare ordering queries.
        agg = ReportAggregation.objects.first()
        max_key = max(agg.value.items(), key=operator.itemgetter(1))[0]
        max_key_percentage = max(agg.value_percentage.items(), key=operator.itemgetter(1))[0]
        orderings = [
            'value__{}'.format(max_key),
            'value_percentage__{}'.format(max_key_percentage),
        ]

        for ordering in orderings:
            # Compute expected order of ID list.
            expected = list(ReportAggregation.objects.all().order_by(ordering).values_list('id', flat=True))

            # Query api and compile resulting order.
            response = self.client.get(url + '&ordering={}'.format(ordering))
            result = response.json()
            self.assertEqual(result['count'], 5)
            result = [dat['id'] for dat in result['results']]

            # Order is as expected.
            self.assertEqual(result, expected)

            # Invert query order.
            response = self.client.get(url + '&ordering=-{}'.format(ordering))
            result = response.json()
            self.assertEqual(result['count'], 5)
            result = [dat['id'] for dat in result['results']]

            # Order is as expected.
            expected = list(ReportAggregation.objects.all().order_by('-' + ordering).values_list('id', flat=True))
            self.assertEqual(result, expected)

        # Query api with double filter argument.
        response = self.client.get(url + '&ordering=-aggregationarea__name,min_date')
        result = response.json()
        self.assertEqual(result['count'], 5)
        result = [dat['id'] for dat in result['results']]
        expected = list(ReportAggregation.objects.all().order_by('-aggregationarea__name', 'min_date').values_list('id', flat=True))
        self.assertEqual(result, expected)

        # Test default sorting.
        response = self.client.get(url)
        result = response.json()
        self.assertEqual(result['count'], 5)
        expected = list(ReportAggregation.objects.all().order_by('aggregationarea__name', 'min_date').values_list('id', flat=True))
        result = [dat['id'] for dat in result['results']]
        self.assertEqual(result, expected)
