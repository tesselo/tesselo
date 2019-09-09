import tempfile

import dateutil
from raster.models import RasterLayer
from raster_aggregation.models import AggregationArea, AggregationLayer

from classify.models import PredictedLayer
from django.contrib.auth.models import User
from django.core.files import File
from django.test import TestCase, override_settings
from formulary.models import Formula
from report.models import ReportAggregation, ReportSchedule
from sentinel import ecs
from sentinel.models import Composite, MGRSTile, SentinelTile, SentinelTileBand


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, LOCAL=True)
class AggregationViewTests(TestCase):

    def setUp(self):
        self.usr = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )
        self.client.login(username='michael', password='bananastand')

        aggfile = tempfile.NamedTemporaryFile(suffix='.zip')

        self.agglayer = AggregationLayer.objects.create(
            name='Testfile',
            name_column='test',
            shapefile=File(open(aggfile.name), name='test.shp.zip')
        )

        self.aggarea = AggregationArea.objects.create(
            name='Testarea',
            aggregationlayer=self.agglayer,

            geom='SRID=3857;MULTIPOLYGON (((-8877202 -296836, -8877302 -296836, -8877302 -296936, -8877202 -296836)))',
        )
        self.aggarea2 = AggregationArea.objects.create(
            name='Testarea 2',
            aggregationlayer=self.agglayer,
            geom='SRID=3857;MULTIPOLYGON (((-8877202 -296836, -8877302 -296836, -8877302 -296936, -8877202 -296836)))',
        )

        self.formula = Formula.objects.create(name='Formula', formula='B2/B3')

        self.composite = Composite.objects.create(
            name='Bananastand December 2015',
            official=True,
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

    def test_create_aggregator_composite(self):
        agg = ReportAggregation.objects.create(
            formula=self.formula,
            composite=self.composite,
            aggregationlayer=self.agglayer,
            aggregationarea=self.aggarea,
        )
        self.assertEqual(agg.valuecountresult.formula, 'B2/B3')
        self.assertEqual(
            agg.valuecountresult.layer_names,
            {
                'B2': self.composite.compositeband_set.get(band='B02.jp2').rasterlayer_id,
                'B3': self.composite.compositeband_set.get(band='B03.jp2').rasterlayer_id,
            }
        )

    def test_create_aggregator_predicted(self):
        agg = ReportAggregation.objects.create(
            formula=self.formula,
            predictedlayer=self.predictedlayer,
            aggregationlayer=self.agglayer,
            aggregationarea=self.aggarea,
        )
        self.assertEqual(
            agg.valuecountresult.layer_names,
            {
                'x': self.predictedlayer.rasterlayer_id,
            }
        )

    def test_report_schedule(self):
        ReportSchedule.objects.create(
            formula=self.formula,
            composite=self.composite,
            aggregationlayer=self.agglayer,
        )
        self.assertEqual(ReportAggregation.objects.count(), 0)
        self.formula.formula = 'B3/B2'
        self.formula.save()
        self.assertEqual(ReportAggregation.objects.count(), 2)

    def test_report_schedule_push(self):
        sc = ReportSchedule.objects.create(
            formula=self.formula,
            composite=self.composite,
            aggregationlayer=self.agglayer,
        )
        ecs.push_reports('reportschedule', sc.id)
        self.assertEqual(ReportAggregation.objects.count(), 2)

    def test_report_schedule_populate(self):
        sc = ReportSchedule.objects.create(
            formula=self.formula,
            composite=self.composite,
            aggregationlayer=self.agglayer,
        )
        ecs.push_reports('reportschedule', sc.id)
        self.assertEqual(ReportAggregation.objects.count(), 2)

    def test_report_schedule_populate_agglayer(self):
        sc = ReportSchedule.objects.create(
            formula=self.formula,
            composite=self.composite,
            aggregationlayer=self.agglayer,
        )
        ecs.push_reports('aggregationlayer', sc.aggregationlayer.id)
        self.assertEqual(ReportAggregation.objects.count(), 2)

    def test_report_schedule_populate_composite(self):
        sc = ReportSchedule.objects.create(
            formula=self.formula,
            composite=self.composite,
            aggregationlayer=self.agglayer,
        )
        ecs.push_reports('composite', sc.composite.id)
        self.assertEqual(ReportAggregation.objects.count(), 2)
