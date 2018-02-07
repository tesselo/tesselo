from __future__ import unicode_literals

import shutil
import tempfile

import mock
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.svm import LinearSVC
from tests.mock_functions import client_get_object, get_numpy_tile, iterator_search, point_to_test_file

from classify.models import Classifier, PredictedLayer, TrainingSample
from classify.tasks import predict_sentinel_layer, train_sentinel_classifier
from django.conf import settings
from django.contrib.gis.gdal import OGRGeometry
from django.core.cache import cache
from django.core.urlresolvers import reverse
from django.test import TestCase, override_settings
from sentinel.models import Composite, SentinelTile, ZoneOfInterest
from sentinel.tasks import drive_composite_builders, drive_sentinel_queue, sync_sentinel_bucket_utm_zone


@mock.patch('sentinel.tasks.botocore.paginate.PageIterator.search', iterator_search)
@mock.patch('sentinel.tasks.boto3.session.Session.client', client_get_object)
@mock.patch('raster.tiles.parser.urlretrieve', point_to_test_file)
@mock.patch('sentinel.tasks.get_tile', get_numpy_tile)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class SentinelClassifierTest(TestCase):

    def setUp(self):
        bbox = [11833687.0, -469452.0, 11859687.0, -441452.0]
        bbox = OGRGeometry.from_bbox(bbox)
        bbox.srid = 3857
        self.zone = ZoneOfInterest.objects.create(name='A zone', geom=bbox.ewkt)
        bbox.transform(4326)
        self.world = Composite.objects.create(name='The World', min_date='2000-01-01', max_date='2100-01-01')
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
        self.clf = Classifier.objects.create(name='Clouds', algorithm=Classifier.SVM)

        self.clf.trainingsamples.add(self.cloud)
        self.clf.trainingsamples.add(self.shadow)
        self.clf.trainingsamples.add(self.cloudfree)

    def _get_data(self):

        sync_sentinel_bucket_utm_zone(1)
        drive_sentinel_queue()
        drive_sentinel_queue()

        tile = SentinelTile.objects.first()

        self.cloud.sentineltile = tile
        self.cloud.save()
        self.shadow.sentineltile = tile
        self.shadow.save()
        self.cloudfree.sentineltile = tile
        self.cloudfree.save()

    def tearDown(self):
        shutil.rmtree(settings.MEDIA_ROOT)

    def test_classifier_training(self):
        self._get_data()
        # SVM
        self.clf.algorithm = Classifier.SVM
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf, LinearSVC))
        cache.clear()

        # Random forest
        self.clf.algorithm = Classifier.RF
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf, RandomForestClassifier))
        cache.clear()

        # Neural Network
        self.clf.algorithm = Classifier.NN
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf, MLPClassifier))
        cache.clear()

    def test_classifier_prediction_sentineltile(self):
        self._get_data()
        pred = PredictedLayer.objects.create(
            sentineltile=SentinelTile.objects.first(),
            classifier=self.clf,
        )
        self.assertEqual(pred.rasterlayer.rastertile_set.count(), 0)
        train_sentinel_classifier(self.clf.id)
        predict_sentinel_layer(pred.id)
        pred.refresh_from_db()
        self.assertTrue(pred.rasterlayer.rastertile_set.count() > 0)
        cache.clear()

    def test_classifier_prediction_composite(self):
        self._get_data()
        drive_composite_builders()
        train_sentinel_classifier(self.clf.id)

        pred = PredictedLayer.objects.create(
            composite=self.world,
            classifier=self.clf,
        )
        predict_sentinel_layer(pred.id)
        pred.refresh_from_db()
        self.assertTrue(pred.rasterlayer.rastertile_set.count() > 0)
        cache.clear()

    def test_cloud_view(self):
        self._get_data()
        scene = SentinelTile.objects.filter(sentineltileband__isnull=False).first()
        band = scene.sentineltileband_set.get(band='B02.jp2')
        tile = band.layer.rastertile_set.first()
        url = reverse('clouds', kwargs={
            'z': tile.tilez, 'y': tile.tiley, 'x': tile.tilex,
            'stile': scene.id, 'frmt': 'png'
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
