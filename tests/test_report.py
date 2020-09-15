import io
import operator
import tempfile
from unittest.mock import patch

import dateutil
from django.contrib.auth.models import User
from django.contrib.gis.gdal import GDALRaster
from django.core.files import File
from django.test import TestCase, override_settings
from django.urls import reverse
from raster.models import RasterLayer, RasterTile
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster_aggregation.models import AggregationArea, AggregationLayer
from tests.mock_functions import patch_get_raster_tile_range_100

from classify.models import PredictedLayer
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

    def _create_report_schedule(self, discrete=False):
        sc = ReportSchedule.objects.create(active=True)
        sc.aggregationlayers.add(self.agglayer)
        if discrete:
            sc.predictedlayers.add(self.predictedlayer)
        else:
            sc.formulas.add(self.formula)
            sc.composites.add(self.composite)
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

    def test_total_area_and_percentage_covered(self):
        # Prepare data.
        ReportAggregation.objects.all().delete()
        AggregationArea.objects.all().delete()
        self.aggarea = AggregationArea.objects.create(
            name='Testarea',
            aggregationlayer=self.agglayer,
            geom='SRID=3857;MultiPolygon (((-933060.78425902221351862 5104392.97558140475302935, -933446.9497359802480787 5104015.69289628323167562, -933578.08012271975167096 5103308.26908933464437723, -933641.19398318068124354 5103302.51773695833981037, -933744.35188680712599307 5103302.33038316480815411, -933833.31302208022680134 5103284.38222409039735794, -933898.73871423199307173 5103252.18539650924503803, -933991.14979464188218117 5103182.27827171236276627, -934044.59435582184232771 5103127.74373328685760498, -934072.63852799334563315 5103087.10762068722397089, -934093.08396912133321166 5103042.21800980158150196, -934108.06840466498397291 5102993.25586444512009621, -934117.52199452719651163 5102939.35106317140161991, -934122.47793211578391492 5102868.62381869554519653, -934129.52260563371237367 5102773.34548014216125011, -934153.94863935385365039 5102613.53802607208490372, -934192.35519908147398382 5102489.1054332684725523, -934219.48966769909020513 5102426.49070599488914013, -934251.4157156350556761 5102367.74840465746819973, -934282.65457988122943789 5102333.55204823520034552, -934289.10973411437589675 5102326.4952385937795043, -934441.39559623424429446 5102201.74466798268258572, -934633.07860985386651009 5102075.11626704502850771, -934759.67424554284662008 5102040.9200991615653038, -934829.59015142789576203 5102035.08729339297860861, -934909.35859468241687864 5102045.89791896287351847, -934965.60786590748466551 5102059.85049568489193916, -935034.80903650622349232 5102094.98137657437473536, -935116.5513370253611356 5102147.59110053069889545, -935188.34191848046611995 5102198.85223614424467087, -935233.51384365616831928 5102248.80186108779162169, -935294.08313447958789766 5102319.77505511231720448, -935306.92373652476817369 5102343.52761244401335716, -935327.121936627314426 5102375.51354151498526335, -935360.74140426504891366 5102411.85491386149078608, -935418.67455429362598807 5102472.09988697525113821, -935483.68036402389407158 5102530.37864760216325521, -935572.09258975472766906 5102587.18828275427222252, -935718.47752108238637447 5102673.22320987191051245, -935716.77591440570540726 5102675.78898413944989443, -935673.33825751859694719 5102740.56635011546313763, -935669.63874073990155011 5102748.95659379661083221, -935667.46001549914944917 5102752.60998157318681479, -935666.13556584983598441 5102755.91159349121153355, -935656.09958975785411894 5102779.16152127180248499, -935647.73028497118502855 5102797.5262917336076498, -935642.49836701422464103 5102806.76542033813893795, -935633.25764650362543762 5102819.78453010320663452, -935629.60160549671854824 5102824.98435447365045547, -935625.43078975367825478 5102832.03507409617304802, -935623.65057685622014105 5102835.23103938717395067, -935618.30846722726710141 5102843.58605366945266724, -935612.02392546716146171 5102853.70055580139160156, -935610.45733638282399625 5102856.66809339262545109, -935586.4375711582833901 5102888.15253852028399706, -935583.00842168740928173 5102893.36493668239563704, -935578.52707907743752003 5102899.49169107712805271, -935576.12218880129512399 5102903.36004756018519402, -935574.85137351742014289 5102906.91703655757009983, -935574.11765952198766172 5102911.35615264531224966, -935573.30937298806384206 5102917.48459349572658539, -935572.83099991292692721 5102926.69619280751794577, -935573.65361260832287371 5102937.63219775445759296, -935574.05333508341573179 5102941.85353068355470896, -935573.60428108857013285 5102947.59209749568253756, -935573.94117424602154642 5102961.13073111791163683, -935572.83057126286439598 5102973.15859058499336243, -935572.25460681994445622 5102976.96784884482622147, -935572.11416080605704337 5102983.08095170557498932, -935572.46117389039136469 5102987.31587635632604361, -935572.39248866692651063 5102990.84202240221202374, -935572.02090160886291414 5102995.81625635363161564, -935571.87246704578865319 5102999.67766237258911133, -935574.53542715369258076 5103022.41813484486192465, -935576.08807506447192281 5103031.99770774971693754, -935581.03239795088302344 5103066.79587366245687008, -935581.39188703743275255 5103075.05276468489319086, -935580.22377241170033813 5103081.34358172491192818, -935579.81913133827038109 5103092.86061583552509546, -935582.69919654459226876 5103112.5435765003785491, -935595.3450391786172986 5103150.11978000495582819, -935608.88077262078877538 5103181.83468607626855373, -935619.05197862244676799 5103205.22133165318518877, -935634.19640312797855586 5103247.44192799832671881, -935636.41820615739561617 5103253.13187899440526962, -935638.69699052697978914 5103260.08221205417066813, -935644.77257848111912608 5103272.36910701543092728, -935653.51873895234894007 5103288.68302639573812485, -935663.80003265966661274 5103313.1161396587267518, -935665.17610744840931147 5103317.54863488115370274, -935671.96710896934382617 5103353.2535416204482317, -935673.33064080635085702 5103357.9416132839396596, -935674.60557120887096971 5103363.92968629766255617, -935675.54554638720583171 5103369.91962802596390247, -935677.94133811083156615 5103379.87209325283765793, -935679.16089210228528827 5103385.36446282640099525, -935680.07942091557197273 5103392.81521518994122744, -935683.85405716777313501 5103404.07807365152984858, -935684.63998988177627325 5103407.62794036883860826, -935686.67515566048678011 5103413.27874850761145353, -935688.72234430781099945 5103418.67480458505451679, -935691.59350556822028011 5103422.98208558838814497, -935734.78525954391807318 5103494.19092760421335697, -935806.44914219982456416 5103585.71298849396407604, -935801.99051889672409743 5103586.35807379335165024, -935802.66239606833551079 5103600.25742430426180363, -935819.51376233971677721 5103598.94334515556693077, -935941.35596028354484588 5103777.39258972089737654, -935725.46815858408808708 5104000.97021981328725815, -935726.77146741247270256 5104171.72925479523837566, -935738.50482187455054373 5104211.41679506842046976, -935747.43467089475598186 5104243.22976262029260397, -935754.0936344179790467 5104262.46163517981767654, -935764.48947392439004034 5104276.42532474268227816, -935762.70227869728114456 5104281.45888704434037209, -935596.58135514450259507 5104411.83850783761590719, -935427.32830605714116246 5104431.26682404335588217, -934912.14479729789309204 5104871.75669271685183048, -934873.25421777681913227 5104904.44597192201763391, -934849.24812209967058152 5104925.38355725258588791, -934842.68867256643716246 5104942.36505780927836895, -934844.82516410003881902 5104959.62751637771725655, -934774.38545993028674275 5105032.12963659409433603, -934502.11578483565244824 5105366.73196384869515896, -934408.42150971409864724 5105318.92225064057856798, -933932.29990028135944158 5105075.83800445962697268, -933908.01924057956784964 5105059.15127155650407076, -933882.27149246039334685 5105048.04623449873179197, -933858.40307674324139953 5105048.66708383057266474, -933822.33324987592641264 5105069.97366564348340034, -933820.74607110978104174 5105070.89029321260750294, -933815.21962362760677934 5105071.91235892940312624, -933821.23289987503085285 5105036.83189134858548641, -933823.11327688209712505 5105022.2918893713504076, -933826.59056800045073032 5104987.87641527596861124, -933826.1815228892955929 5104980.58364438451826572, -933821.26516839838586748 5104957.88462105393409729, -933820.70621337194461375 5104954.199276402592659, -933820.56003612524364144 5104949.97637501172721386, -933820.64054571627639234 5104945.61845058109611273, -933820.98930392763577402 5104941.6749839773401618, -933822.79062036809045821 5104931.98954348545521498, -933426.52510541677474976 5104642.74179768934845924, -933060.78425902221351862 5104392.97558140475302935)))',  # Dicofre 030102
        )
        # Compute statistics.
        self._create_report_schedule(discrete=True)
        rasrid = ReportAggregationLayerSrid.objects.create(aggregationlayer=self.agglayer, srid=3763)
        push_reports('aggregationlayer', self.agglayer.id)
        # Percentage cover is close to one (given a pixel resolution error).
        agg = ReportAggregation.objects.first()
        self.assertAlmostEqual(sum([float(val) for val in agg.value.values()]), 298.6503408, 1)
        self.assertAlmostEqual(agg.stats_percentage_covered, 1, 3)
        # Same in SRID 3857.
        agg = ReportAggregation.objects.all().delete()
        rasrid.srid = 3857
        rasrid.save()
        push_reports('aggregationlayer', self.agglayer.id)
        # Percentage cover is close to one (given a pixel resolution error).
        agg = ReportAggregation.objects.first()
        self.assertAlmostEqual(sum([float(val) for val in agg.value.values()]), 534.7698016, 1)
        self.assertAlmostEqual(agg.stats_percentage_covered, 1, 3)

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
