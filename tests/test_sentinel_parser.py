from __future__ import unicode_literals

import shutil
import tempfile

import mock
from raster.models import RasterLayer, RasterTile

from django.conf import settings
from django.contrib.gis.gdal import OGRGeometry
from django.core.urlresolvers import reverse
from django.db.models import Count
from django.test import TestCase, override_settings
from sentinel import const
from sentinel.models import (
    BucketParseLog, MGRSTile, SentinelTile, SentinelTileBand, WorldLayerGroup, WorldParseProcess, ZoneOfInterest
)
from sentinel.tasks import (
    drive_sentinel_queue, drive_world_layers, repair_incomplete_scenes, sync_sentinel_bucket_utm_zone
)
from tests.mock_functions import client_get_object, iterator_search, point_to_test_file
from classify.models import Classifier, TrainingSample
from classify.tasks import train_cloud_classifier


@mock.patch('sentinel.tasks.botocore.paginate.PageIterator.search', iterator_search)
@mock.patch('sentinel.tasks.boto3.session.Session.client', client_get_object)
@mock.patch('raster.tiles.parser.urlretrieve', point_to_test_file)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class SentinelBucketParserTest(TestCase):

    def setUp(self):
        bbox = [650000, 9530240, 660000, 9650040]
        bbox = OGRGeometry.from_bbox(bbox)
        bbox.srid = 32748
        self.zone = ZoneOfInterest.objects.create(name='A zone', geom=bbox.ewkt)
        self.world = WorldLayerGroup.objects.create(name='The World', min_date='2000-01-01', max_date='2100-01-01')
        self.world.zonesofinterest.add(self.zone)
        settings.MEDIA_ROOT = tempfile.mkdtemp()

        self.cloud = TrainingSample.objects.create(
            geom='SRID=3857;POLYGON((11844687 -459865, 11844697 -459865, 11844697 -459805, 11844687 -459805, 11844687 -459865))',
            category='Cloud',
            value=2,
        )
        self.shadow = TrainingSample.objects.create(
            geom='SRID=3857;POLYGON((11844787 -459865, 11844797 -459865, 11844797 -459805, 11844787 -459805, 11844787 -459865))',
            category='Shadow',
            value=1
        )
        self.cloudfree = TrainingSample.objects.create(
            geom='SRID=3857;POLYGON((11844887 -459865, 11844897 -459865, 11844897 -459805, 11844887 -459805, 11844887 -459865))',
            category='Cloud free',
            value=0,
        )
        self.clf = Classifier.objects.create(name='Clouds', algorithm='svm')

        # (11843687.0, -460775.1108485553, 11846010.110848555, -458452.0)
        self.clf.trainingsamples.add(self.cloud)
        self.clf.trainingsamples.add(self.shadow)
        self.clf.trainingsamples.add(self.cloudfree)

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
        self.assertListEqual(
            [x for x in result],
            [(13, 24), (11, 6), (14, 32)],
        )

    def _assign_sentineltile(self):
        sent = SentinelTile.objects.first()

        self.cloud.sentineltile = sent
        self.cloud.save()
        self.shadow.sentineltile = sent
        self.shadow.save()
        self.cloudfree.sentineltile = sent
        self.cloudfree.save()

    def test_cloud_training(self):
        # Worldlayer objects have been created.
        sync_sentinel_bucket_utm_zone(1)
        drive_sentinel_queue()

        self._assign_sentineltile()

        train_cloud_classifier(self.clf.id)

        self.clf.refresh_from_db()

        self.assertTrue(self.clf.trained is not None)


    def test_world_layer(self):
        # Worldlayer objects have been created.
        sync_sentinel_bucket_utm_zone(1)
        self.assertEqual(self.world.worldlayers.count(), len(const.BAND_CHOICES))

        lyr = RasterLayer.objects.get(name='The World - B02.jp2')
        self.assertEqual(lyr.rastertile_set.count(), 0)

        drive_sentinel_queue()
        drive_sentinel_queue()

        self._assign_sentineltile()
        train_cloud_classifier(self.clf.id)

        drive_world_layers()

        self.assertTrue(RasterTile.objects.filter(rasterlayer_id=lyr.id).count() > 0)
        self.assertTrue(RasterTile.objects.filter(tilez=5, rasterlayer_id=lyr.id).count() > 0)

        self.world.refresh_from_db()
        indexrange = self.zone.index_range(const.ZOOM_LEVEL_WORLDLAYER)
        processed = WorldParseProcess.objects.filter(
            worldlayergroup=self.world,
            tilex=indexrange[0],
            tiley=indexrange[1],
            tilez=const.ZOOM_LEVEL_WORLDLAYER,
            end__isnull=False,
        )
        processing = WorldParseProcess.objects.filter(
            worldlayergroup=self.world,
            end__isnull=True,
        )
        self.assertTrue(processed.exists())
        self.assertFalse(processing.exists())

        self.assertEqual(lyr.rastertile_set.count(), 20)

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

    def test_cloud_view(self):
        sync_sentinel_bucket_utm_zone(1)
        drive_sentinel_queue()
        drive_sentinel_queue()
        scene = SentinelTile.objects.filter(sentineltileband__isnull=False).first()
        band = scene.sentineltileband_set.get(band='B02.jp2')
        tile = band.layer.rastertile_set.first()
        url = reverse('clouds', kwargs={
            'z': tile.tilez, 'y': tile.tiley, 'x': tile.tilex,
            'stile': scene.id, 'frmt': 'png'
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
