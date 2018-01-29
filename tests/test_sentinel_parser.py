from __future__ import unicode_literals

import shutil
import tempfile

import mock
from raster.models import RasterTile
from tests.mock_functions import client_get_object, get_numpy_tile, iterator_search, point_to_test_file

from django.conf import settings
from django.contrib.gis.gdal import OGRGeometry
from django.db.models import Count
from django.test import TestCase, override_settings
from sentinel import const
from sentinel.models import (
    BucketParseLog, Composite, CompositeBuildLog, MGRSTile, SentinelTile, SentinelTileBand, ZoneOfInterest
)
from sentinel.tasks import (
    drive_sentinel_queue, drive_world_layers, repair_incomplete_scenes, sync_sentinel_bucket_utm_zone
)


@mock.patch('sentinel.tasks.botocore.paginate.PageIterator.search', iterator_search)
@mock.patch('sentinel.tasks.boto3.session.Session.client', client_get_object)
@mock.patch('sentinel.tasks.get_tile', get_numpy_tile)
@mock.patch('raster.tiles.parser.urlretrieve', point_to_test_file)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class SentinelBucketParserTest(TestCase):

    def setUp(self):
        bbox = [11833687.0, -469452.0, 11859687.0, -441452.0]
        bbox = OGRGeometry.from_bbox(bbox)
        bbox.srid = 3857
        self.zone = ZoneOfInterest.objects.create(name='A zone', geom=bbox.ewkt)
        bbox.transform(4326)
        self.world = Composite.objects.create(name='The World', min_date='2000-01-01', max_date='2100-01-01')
        self.world.zonesofinterest.add(self.zone)

        settings.MEDIA_ROOT = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(settings.MEDIA_ROOT)

    def test_parser(self):
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

    def test_queue_driver(self):
        sync_sentinel_bucket_utm_zone(1)
        drive_sentinel_queue()
        bnd = SentinelTileBand.objects.filter(band=const.BD1).first()
        self.assertEqual(bnd.resolution, const.BAND_RESOLUTIONS[const.BD1])
        result = RasterTile.objects.all().values_list('tilez').annotate(count=Count('tilez'))

        self.assertEqual(
            {x[0]: x[1] for x in result},
            {
                8: 26,
                13: 40,
                11: 26,
                14: 32,
                12: 40,
                10: 26,
                9: 26,
                6: 26,
                7: 26,
            }
        )

    def test_world_layer(self):
        sync_sentinel_bucket_utm_zone(1)
        self.assertEqual(self.world.compositebands.count(), len(const.BAND_CHOICES))

        lyr = self.world.compositebands.filter(rasterlayer__name='The World - B02.jp2').first().rasterlayer

        self.assertEqual(lyr.rastertile_set.count(), 0)

        drive_sentinel_queue()
        drive_sentinel_queue()

        drive_world_layers()

        self.assertTrue(RasterTile.objects.filter(rasterlayer_id=lyr.id).count() > 0)
        self.assertTrue(RasterTile.objects.filter(tilez=5, rasterlayer_id=lyr.id).count() > 0)

        self.world.refresh_from_db()
        indexrange = self.zone.index_range(const.ZOOM_LEVEL_WORLDLAYER)
        processed = CompositeBuildLog.objects.filter(
            composite=self.world,
            tilex=indexrange[0],
            tiley=indexrange[1],
            tilez=const.ZOOM_LEVEL_WORLDLAYER,
            end__isnull=False,
        )
        processing = CompositeBuildLog.objects.filter(
            composite=self.world,
            end__isnull=True,
        )
        self.assertTrue(processed.exists())
        self.assertFalse(processing.exists())

        self.assertEqual(lyr.rastertile_set.count(), 522)

    def test_scene_completness_repair(self):
        sync_sentinel_bucket_utm_zone(1)
        drive_sentinel_queue()
        # Delete one tile band.
        band = SentinelTileBand.objects.first()
        scene = band.tile
        band.delete()
        scene.refresh_from_db()
        self.assertEqual(
            scene.sentineltileband_set.count(),
            const.NR_OF_BANDS - 1,
        )
        # Repair incomplete scene.
        repair_incomplete_scenes()
        # Assert scene has been updated.
        scene.refresh_from_db()
        self.assertEqual(
            scene.sentineltileband_set.count(),
            const.NR_OF_BANDS,
        )

    def test_public_rasterlayer(self):
        """
        The sentinel band rasterlayer is public after creation.
        """
        sync_sentinel_bucket_utm_zone(1)
        drive_sentinel_queue()
        for tile in SentinelTileBand.objects.all():
            self.assertTrue(tile.layer.publicrasterlayer.public)
