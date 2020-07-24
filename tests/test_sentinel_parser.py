import os
import shutil
import tempfile
from unittest import skip
from unittest.mock import patch

from raster_aggregation.models import AggregationArea, AggregationLayer
from tests.mock_functions import (
    client_get_object, iterator_search, patch_get_raster_tile, patch_process_l2a, patch_snap_terrain_correction,
    patch_write_raster_tile, point_to_test_file
)

from classify.models import Classifier
from django.conf import settings
from django.contrib.gis.gdal import OGRGeometry
from django.core.files import File
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings
from sentinel import const
from sentinel.models import (
    BucketParseLog, Composite, CompositeBuild, CompositeTile, MGRSTile, SentinelTile, SentinelTileBand
)
from sentinel.tasks import (
    clear_composite, clear_sentineltile, composite_build_callback, generate_bands_and_sceneclass,
    sync_sentinel_bucket_utm_zone
)
from sentinel_1 import const as s1const
from sentinel_1.models import Sentinel1Tile


@patch('sentinel.tasks.boto3.session.botocore.paginate.PageIterator.search', iterator_search)
@patch('sentinel.tasks.boto3.session.Session.client', client_get_object)
@patch('sentinel.tasks.get_raster_tile', patch_get_raster_tile)
@patch('sentinel.tasks.write_raster_tile', patch_write_raster_tile)
@patch('raster.tiles.parser.urlretrieve', point_to_test_file)
@patch('jobs.ecs.process_l2a', patch_process_l2a)
@patch('jobs.ecs.snap_terrain_correction', patch_snap_terrain_correction)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, LOCAL=True)
class SentinelBucketParserTest(TestCase):

    def setUp(self):
        bbox = [11833687.0, -469452.0, 11859687.0, -441452.0]
        bbox = OGRGeometry.from_bbox(bbox)
        bbox.srid = 3857
        self.agglayer = AggregationLayer.objects.create(name='Test Agg Layer')
        self.zone = AggregationArea.objects.create(
            name='Test Agg Area',
            aggregationlayer=self.agglayer,
            geom='SRID=3857;MULTIPOLYGON((( 11833687 -469452, 11833797 -469452, 11833797 -469352, 11833687 -469352, 11833687 -469452 )))',
        )
        self.s1scene = Sentinel1Tile.objects.create(
            product_name='Test',
            prefix='test',
            mission_id='test',
            product_type='GRD',
            mode='IW',
            polarization='DV',
            start_time='2005-01-01',
            stop_time='2005-01-01',
            absolute_orbit_number=1,
            mission_datatake_id=1,
            product_unique_identifier='test',
            sci_hub_id='test',
            footprint='SRID=3857;MULTIPOLYGON((( 11833687 -469452, 11833797 -469452, 11833797 -469352, 11833687 -469352, 11833687 -469452 )))',
            filename_map={},
            status=Sentinel1Tile.UNPROCESSED,
            log='',
        )

        self.composite = Composite.objects.create(name='The World', min_date='2000-01-01', max_date='2100-01-01')
        self.build = CompositeBuild.objects.create(
            composite=self.composite,
            aggregationlayer=self.agglayer,
            include_sentinel_1=False,
            include_sentinel_2=True,
        )

        settings.MEDIA_ROOT = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(settings.MEDIA_ROOT)

    def test_sentinelbuild_set_sentineltiles(self):
        sync_sentinel_bucket_utm_zone(1)
        self.build.set_sentineltiles()
        self.assertEqual(self.build.sentineltiles.count(), 3)

    def test_sentinelbuild_set_compositetiles(self):
        sync_sentinel_bucket_utm_zone(1)
        self.build.set_compositetiles()
        self.assertEqual(self.build.compositetiles.count(), 1)

    @skip('This test interacts with the others and the files are not found. Runs ok individually.')
    def test_scene_ingesion(self):
        sync_sentinel_bucket_utm_zone(1)
        composite_build_callback(self.build.id, initiate=True, rebuild=True)
        band = SentinelTileBand.objects.filter(band=const.BD2).first()
        path = 'tiles/{}/14'.format(band.layer.id)
        subpath = os.path.join(path, default_storage.listdir(path)[0][0])
        # Files have been created (RasterTiles are not tracked on the DB level
        # anymore).
        self.assertEqual(default_storage.listdir(subpath)[1], ['8372.tif'])

    def test_process_compositetile(self):
        sync_sentinel_bucket_utm_zone(1)
        self.build.include_sentinel_1 = True
        self.build.include_sentinel_2 = True
        self.build.save()
        # Calling build callback. In testing mode there are no internal
        # callbacks, so this function needs to be called three times.
        # 1. Ingest scenes
        # 2. Build Composite Tiles
        # 3. Write success flag
        self.assertEqual(self.build.status, CompositeBuild.UNPROCESSED)
        composite_build_callback(self.build.id, initiate=True, rebuild=True)
        self.build.refresh_from_db()
        self.assertEqual(self.build.status, CompositeBuild.INGESTING_SCENES)
        composite_build_callback(self.build.id, initiate=False)
        self.build.refresh_from_db()
        self.assertEqual(self.build.status, CompositeBuild.FINISHED)
        # Get ctile to check progress.
        ctile = self.build.compositetiles.first()
        # Comments have been written to the log.
        self.assertIn('Scheduled composite builder, waiting for worker availability.', ctile.log)
        self.assertIn('Starting to build composite at max zoom level.', ctile.log)
        self.assertIn('Finished building composite tile at max zoom level, starting Pyramid.', ctile.log)
        self.assertIn('Using S2 cloud removal algorithm Version ', ctile.log)
        self.assertIn('Finished building composite tile.', ctile.log)
        # The status has been set to finished.
        self.assertEqual(ctile.status, CompositeTile.FINISHED)
        # Check that the S1 tiles have been created.
        band = self.composite.compositeband_set.get(band=s1const.BDVV)
        path = 'tiles/{}/14'.format(band.rasterlayer.id)
        # Composite raster tile files have been created (RasterTiles are not
        # tracked on the DB level anymore).
        expected = [
            '8368.tif',
            '8369.tif',
            '8370.tif',
            '8371.tif',
            '8372.tif',
            '8373.tif',
            '8374.tif',
            '8375.tif',
            '8376.tif',
            '8377.tif',
            '8378.tif',
            '8379.tif',
            '8380.tif',
            '8381.tif',
            '8382.tif',
            '8383.tif',
        ]
        self.assertEqual(
            sorted(default_storage.listdir(os.path.join(path, default_storage.listdir(path)[0][0]))[1]),
            expected,
        )
        # Check that the S2 tiles have been created.
        band = self.composite.compositeband_set.get(band=const.BD2)
        path = 'tiles/{}/14'.format(band.rasterlayer.id)
        # Composite raster tile files have been created (RasterTiles are not
        # tracked on the DB level anymore).
        self.assertEqual(
            sorted(default_storage.listdir(os.path.join(path, default_storage.listdir(path)[0][0]))[1]),
            expected,
        )
        # Run the classifier based version.
        with open('tests/data/classifier-1.pickle', 'rb') as fl:
            self.build.cloud_classifier = Classifier.objects.create(name='Test', trained=File(fl))
            self.build.save()
        composite_build_callback(self.build.id, rebuild=True)
        ctile.refresh_from_db()
        self.assertIn('Using S2 cloud removal algorithm Classifier ', ctile.log)
        # Test clearning of sentinel tile.
        stile = SentinelTile.objects.first()
        for band in stile.sentineltileband_set.all():
            self.assertTrue(band.layer.rastertile_set.count() > 0)
        self.assertEqual(stile.status, SentinelTile.FINISHED)
        clear_sentineltile(stile.id)
        for band in stile.sentineltileband_set.all():
            self.assertEqual(band.layer.rastertile_set.count(), 0)
        stile.refresh_from_db()
        self.assertEqual(stile.status, SentinelTile.UNPROCESSED)

    def test_bucket_parser(self):
        sync_sentinel_bucket_utm_zone(1)
        # Check mgrs
        self.assertEqual(MGRSTile.objects.count(), 3)
        mgrs = MGRSTile.objects.get(utm_zone=1)
        self.assertEqual(mgrs.code, '1CCV')
        # Check tile
        self.assertEqual(SentinelTile.objects.count(), 4)
        tile = SentinelTile.objects.get(mgrstile__utm_zone=1)
        self.assertEqual(tile.prefix, 'tiles/1/C/CV/2015/12/21/0/')
        self.assertEqual(tile.cloudy_pixel_percentage, 62.59)
        self.assertEqual(tile.data_coverage_percentage, 91.94)
        # Check parse log
        log = BucketParseLog.objects.first()
        self.assertEqual(log.utm_zone, '1')
        self.assertTrue('Started parsing utm zone "1".' in log.log)
        self.assertTrue(tile.prefix in log.log)
        self.assertTrue('Finished parsing, 4 tiles created.' in log.log)

    def test_public_rasterlayer(self):
        """
        The sentinel band rasterlayer is public after creation.
        """
        sync_sentinel_bucket_utm_zone(1)
        for tile in SentinelTileBand.objects.all():
            self.assertTrue(tile.layer.publicrasterlayer.public)

    def test_filelist_generator(self):
        sync_sentinel_bucket_utm_zone(1)
        tile = SentinelTile.objects.first()
        layer_list = [dat[:2] for dat in generate_bands_and_sceneclass(tile)]
        self.assertEqual(layer_list, [
            ('B01.jp2', 11),
            ('B02.jp2', 14),
            ('B03.jp2', 14),
            ('B04.jp2', 14),
            ('B05.jp2', 13),
            ('B06.jp2', 13),
            ('B07.jp2', 13),
            ('B08.jp2', 14),
            ('B8A.jp2', 13),
            ('B09.jp2', 11),
            ('B10.jp2', 11),
            ('B11.jp2', 13),
            ('B12.jp2', 13),
            ('SCL.jp2', 13),
        ])

    def test_clear_composite(self):
        CompositeTile.objects.create(composite=self.composite, tilez=4, tilex=23, tiley=23)
        clear_composite(self.composite.id)
        self.build.refresh_from_db()
        # Build status is set to cleared.
        self.assertEqual(self.build.status, CompositeBuild.CLEARED)
        # Composite tile was cleared.
        self.assertEqual(self.composite.compositetile_set.count(), 0)
