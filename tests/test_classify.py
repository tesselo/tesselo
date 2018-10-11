import shutil
import tempfile
from unittest import skip

import mock
from raster_aggregation.models import AggregationArea, AggregationLayer
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler
from sklearn.svm import LinearSVC
from tests.mock_functions import (
    client_get_object, get_numpy_tile, iterator_search, patch_process_l2a, patch_write_raster_tile, point_to_test_file
)

from classify.models import (
    Classifier, PredictedLayer, PredictedLayerChunk, TrainingLayer, TrainingLayerExport, TrainingSample
)
from classify.tasks import (
    VALUE_CONFIG_ERROR_MSG, export_training_data, predict_sentinel_layer, train_sentinel_classifier
)
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.gdal import OGRGeometry
from django.test import TestCase, override_settings
from django.urls import reverse
from sentinel.models import Composite, CompositeBuild, SentinelTile
from sentinel.tasks import composite_build_callback, sync_sentinel_bucket_utm_zone


@mock.patch('sentinel.tasks.boto3.session.botocore.paginate.PageIterator.search', iterator_search)
@mock.patch('sentinel.tasks.boto3.session.Session.client', client_get_object)
@mock.patch('raster.tiles.parser.urlretrieve', point_to_test_file)
@mock.patch('sentinel.tasks.get_raster_tile', get_numpy_tile)
@mock.patch('sentinel.tasks.write_raster_tile', patch_write_raster_tile)
@mock.patch('classify.tasks.get_raster_tile', get_numpy_tile)
@mock.patch('classify.tasks.write_raster_tile', patch_write_raster_tile)
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
        self.composite = Composite.objects.create(
            name='The World',
            official=True,
            min_date='2015-12-01',
            max_date='2015-12-31',
        )
        self.build = CompositeBuild.objects.create(
            composite=self.composite,
            aggregationlayer=self.agglayer,
        )

        settings.MEDIA_ROOT = tempfile.mkdtemp()

        self.traininglayer = TrainingLayer.objects.create(name='Test Training Layer')

        self.cloud = TrainingSample.objects.create(
            geom='SRID=3857;POLYGON((11844687 -459865, 11844697 -459865, 11844697 -459805, 11844687 -459805, 11844687 -459865))',
            category='Cloud',
            value=2,
            traininglayer=self.traininglayer,
            composite=self.composite,
        )
        self.shadow = TrainingSample.objects.create(
            geom='SRID=3857;POLYGON((11844787 -459865, 11844797 -459865, 11844797 -459805, 11844787 -459805, 11844787 -459865))',
            category='Shadow',
            value=1,
            traininglayer=self.traininglayer,
            composite=self.composite,
        )
        self.cloudfree = TrainingSample.objects.create(
            geom='SRID=3857;POLYGON((11844887 -459865, 11844897 -459865, 11844897 -459805, 11844887 -459805, 11844887 -459865))',
            category='Cloud free',
            value=0,
            traininglayer=self.traininglayer,
            composite=self.composite,
        )

        self.clf = Classifier.objects.create(
            name='Clouds',
            algorithm=Classifier.RF,
            traininglayer=self.traininglayer,
            splitfraction=0.4,
        )

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
        self.clf.status = self.clf.UNPROCESSED
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf, Pipeline))
        self.assertTrue(isinstance(self.clf.clf.steps[0][1], RobustScaler))
        self.assertTrue(isinstance(self.clf.clf.steps[1][1], LinearSVC))
        self.assertEqual(self.clf.status, self.clf.FINISHED)
        self.assertIn('Finished training algorithm', self.clf.log)

        # Random forest with custom composite set.
        self.clf.algorithm = Classifier.RF
        self.clf.status = self.clf.UNPROCESSED
        self.clf.composite = self.composite
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf.steps[1][1], RandomForestClassifier))
        self.assertEqual(self.clf.status, self.clf.FINISHED)

        # Neural Network
        self.clf.algorithm = Classifier.NN
        self.clf.status = self.clf.UNPROCESSED
        self.clf.composite = None
        self.clf.clf_args = {'max_iter': 500}
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf.steps[1][1], MLPClassifier))
        self.assertEqual(self.clf.status, self.clf.FINISHED)

        # Assert legend was created.
        self.assertEqual(self.clf.traininglayer.legend, {'0': 'Cloud free', '1': 'Shadow', '2': 'Cloud'})

        # Assert accuracy statistic has been calculated.
        self.assertNotEqual(self.clf.classifieraccuracy.accuracy_score, 0)

        # Error due to broken input data.
        self.cloud.pk = None
        self.cloud.value = 99
        self.cloud.save()
        with self.assertRaisesMessage(ValueError, VALUE_CONFIG_ERROR_MSG):
            train_sentinel_classifier(self.clf.id)
        try:
            train_sentinel_classifier(self.clf.id)
        except ValueError:
            self.clf.refresh_from_db()
            self.assertEqual(self.clf.status, Classifier.FAILED)

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

    def test_classifier_prediction_composite_aggregationlayer(self):
        self._get_data()
        train_sentinel_classifier(self.clf.id)

        # Test with compisite range.
        pred = PredictedLayer.objects.create(
            composite=self.composite,
            classifier=self.clf,
        )
        predict_sentinel_layer(pred.id)
        pred.refresh_from_db()
        # Tiles have been created.
        self.assertTrue(pred.rasterlayer.rastertile_set.count() > 0)
        # Pyramid has been built.
        self.assertTrue(pred.predictedlayerchunk_set.count() > 0)
        self.assertEqual(
            pred.predictedlayerchunk_set.count(),
            pred.predictedlayerchunk_set.filter(status=PredictedLayerChunk.FINISHED).count(),
        )
        self.assertEqual(pred.status, PredictedLayer.FINISHED)
        self.assertIn('Finished layer prediction at full resolution', pred.log)
        self.assertIn('Finished building pyramid', pred.log)
        self.assertEqual(pred.status, pred.FINISHED)
        # Test with aggregationlayer argument.
        pred = PredictedLayer.objects.create(
            aggregationlayer=self.agglayer,
            composite=self.composite,
            classifier=self.clf,
        )
        predict_sentinel_layer(pred.id)
        pred.refresh_from_db()
        # Tiles have been created.
        self.assertTrue(pred.rasterlayer.rastertile_set.count() > 0)
        # Pyramid has been built.
        self.assertTrue(pred.predictedlayerchunk_set.count() > 0)
        self.assertEqual(
            pred.predictedlayerchunk_set.count(),
            pred.predictedlayerchunk_set.filter(status=PredictedLayerChunk.FINISHED).count(),
        )
        self.assertIn('Finished layer prediction at full resolution', pred.log)
        self.assertIn('Finished building pyramid', pred.log)
        self.assertEqual(pred.status, pred.FINISHED)

    def test_training_export(self):
        self._get_data()
        # Get rasterlayer id.
        band_names = ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B8A', 'RL{}'.format(self.composite.compositeband_set.first().rasterlayer_id)]
        # Run export task.
        export_training_data(self.clf.traininglayer.id, '2015-12-01', '2015-12-31', band_names)
        export = TrainingLayerExport.objects.filter(traininglayer=self.clf.traininglayer.id).first()
        self.assertTrue(len(export.data.read()) > 2500)

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

    def test_classifier_report_and_list_views(self):
        self._get_data()
        # Train SVM classifier.
        self.clf.algorithm = Classifier.SVM
        self.clf.status = self.clf.UNPROCESSED
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        # Create and authenticate user.
        self.michael = User.objects.create_superuser(
            username='michael',
            email='michael@bluth.com',
            password='bananastand',
        )
        self.client.login(username='michael', password='bananastand')
        # Get url.
        url = reverse('classifier-report', kwargs={'pk': self.clf.id})
        # Request tile build.
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('Producers Accuracy', response.content.decode())
        # Test list rendering.
        url = reverse('classifier-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertNotEqual(data['results'][0]['classifieraccuracy']['cohen_kappa'], 0)
