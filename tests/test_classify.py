import shutil
import tempfile
from unittest import skip

import mock
from raster_aggregation.models import AggregationArea, AggregationLayer
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.svm import LinearSVC
from tests.mock_functions import (
    client_get_object, get_numpy_tile, iterator_search, patch_process_l2a, point_to_test_file
)

from classify.models import Classifier, PredictedLayer, TrainingLayer, TrainingSample
from classify.tasks import predict_sentinel_layer, train_sentinel_classifier
from django.conf import settings
from django.contrib.gis.gdal import OGRGeometry
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from sentinel.models import Composite, CompositeBuild, SentinelTile
from sentinel.tasks import composite_build_callback, sync_sentinel_bucket_utm_zone


@mock.patch('sentinel.tasks.botocore.paginate.PageIterator.search', iterator_search)
@mock.patch('sentinel.tasks.boto3.session.Session.client', client_get_object)
@mock.patch('raster.tiles.parser.urlretrieve', point_to_test_file)
@mock.patch('sentinel.tasks.get_raster_tile', get_numpy_tile)
@mock.patch('sentinel.ecs.process_l2a', patch_process_l2a)
@mock.patch('sys.stdout.write', lambda x: None)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, LOCAL=True)
class SentinelClassifierTest(TestCase):

    def setUp(self):
        bbox = [11833687.0, -469452.0, 11859687.0, -441452.0]
        bbox = OGRGeometry.from_bbox(bbox)
        bbox.srid = 3857
        self.agglayer = AggregationLayer.objects.create(name='Test Agg Layer')
        self.zone = AggregationArea.objects.create(
            name='Test Agg Area',
            aggregationlayer=self.agglayer,
            geom='SRID=3857;MULTIPOLYGON((( 11833687.0 -469452.0, 11833787.0 -469452.0, 11833787.0 -469352.0, 11833687.0 -469352.0, 11833687.0 -469452.0)))'
        )
        self.composite = Composite.objects.create(name='The World', min_date='2000-01-01', max_date='2100-01-01')
        self.build = CompositeBuild.objects.create(composite=self.composite, aggregationlayer=self.agglayer)

        settings.MEDIA_ROOT = tempfile.mkdtemp()

        self.traininglayer = TrainingLayer.objects.create(name='Test Training Layer')

        self.cloud = TrainingSample.objects.create(
            geom='SRID=3857;POLYGON((11844687 -459865, 11844697 -459865, 11844697 -459805, 11844687 -459805, 11844687 -459865))',
            category='Cloud',
            value=2,
            traininglayer=self.traininglayer,
        )
        self.shadow = TrainingSample.objects.create(
            geom='SRID=3857;POLYGON((11844787 -459865, 11844797 -459865, 11844797 -459805, 11844787 -459805, 11844787 -459865))',
            category='Shadow',
            value=1,
            traininglayer=self.traininglayer,
        )
        self.cloudfree = TrainingSample.objects.create(
            geom='SRID=3857;POLYGON((11844887 -459865, 11844897 -459865, 11844897 -459805, 11844887 -459805, 11844887 -459865))',
            category='Cloud free',
            value=0,
            traininglayer=self.traininglayer,
        )

        self.clf = Classifier.objects.create(name='Clouds', algorithm=Classifier.SVM, traininglayer=self.traininglayer)

        self.clf.traininglayer.trainingsample_set.add(self.cloud)
        self.clf.traininglayer.trainingsample_set.add(self.shadow)
        self.clf.traininglayer.trainingsample_set.add(self.cloudfree)

    def tearDown(self):
        shutil.rmtree(settings.MEDIA_ROOT)

    def _get_data(self):
        sync_sentinel_bucket_utm_zone(1)
        composite_build_callback(self.build.id, initiate=True, rebuild=True)
        composite_build_callback(self.build.id, initiate=False)
        self.cloud.composite = self.composite
        self.cloud.save()
        self.shadow.composite = self.composite
        self.shadow.save()
        self.cloudfree.composite = self.composite
        self.cloudfree.save()

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

    @skip('This test setup does not populate the sentineltiles yet.')
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
        train_sentinel_classifier(self.clf.id)

        pred = PredictedLayer.objects.create(
            composite=self.composite,
            classifier=self.clf,
        )
        predict_sentinel_layer(pred.id)
        pred.refresh_from_db()
        # Tiles have been created.
        self.assertTrue(pred.rasterlayer.rastertile_set.count() > 0)
        # Pyramid has been built.
        self.assertTrue(pred.chunks_count > 0)
        self.assertEqual(pred.chunks_done, pred.chunks_count)
        cache.clear()

    @skip('Cloud view is outdated.')
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
