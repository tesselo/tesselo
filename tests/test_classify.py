import shutil
import tempfile
from unittest import skip
from unittest.mock import patch

import numpy
from keras.layers import GRU, BatchNormalization, Dense, Dropout
from keras.models import Sequential
from keras.wrappers.scikit_learn import KerasClassifier
from raster_aggregation.models import AggregationArea, AggregationLayer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler
from sklearn.svm import SVC, SVR, LinearSVC, LinearSVR
from tests.mock_functions import (
    client_get_object, iterator_search, patch_get_raster_tile, patch_process_l2a, patch_write_raster_tile,
    point_to_test_file
)

from classify.const import PREDICTION_CONFIG_ERROR_MSG, VALUE_CONFIG_ERROR_MSG
from classify.models import (
    Classifier, PredictedLayer, PredictedLayerChunk, TrainingLayer, TrainingLayerExport, TrainingSample
)
from classify.tasks import export_training_data, predict_sentinel_layer, train_sentinel_classifier
from classify.utils import RNNRobustScaler
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.gdal import OGRGeometry
from django.test import TestCase, override_settings
from django.urls import reverse
from sentinel.models import Composite, CompositeBuild, SentinelTile
from sentinel.tasks import composite_build_callback, sync_sentinel_bucket_utm_zone


@patch('sentinel.tasks.boto3.session.botocore.paginate.PageIterator.search', iterator_search)
@patch('sentinel.tasks.boto3.session.Session.client', client_get_object)
@patch('raster.tiles.parser.urlretrieve', point_to_test_file)
@patch('sentinel.tasks.get_raster_tile', patch_get_raster_tile)
@patch('sentinel.tasks.write_raster_tile', patch_write_raster_tile)
@patch('classify.tasks.get_raster_tile', patch_get_raster_tile)
@patch('classify.tasks.write_raster_tile', patch_write_raster_tile)
@patch('sentinel.ecs.process_l2a', patch_process_l2a)
@patch('sys.stdout.write', lambda x: None)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, LOCAL=True)
class SentinelClassifierTest(TestCase):

    def setUp(self):
        settings.MEDIA_ROOT = tempfile.mkdtemp()

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
        self.composite2 = Composite.objects.create(
            name='The World 2',
            official=True,
            min_date='2016-01-01',
            max_date='2016-01-31',
        )
        self.build = CompositeBuild.objects.create(
            composite=self.composite,
            aggregationlayer=self.agglayer,
        )
        self.build2 = CompositeBuild.objects.create(
            composite=self.composite2,
            aggregationlayer=self.agglayer,
        )

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

        self.cloud.composite = self.composite
        self.cloud.save()
        self.shadow.composite = self.composite
        self.shadow.save()
        self.cloudfree.composite = self.composite
        self.cloudfree.save()

    def tearDown(self):
        try:
            shutil.rmtree(settings.MEDIA_ROOT)
        except:
            pass

    def _get_data(self):
        sync_sentinel_bucket_utm_zone(1)
        composite_build_callback(self.build.id, initiate=True, rebuild=True)
        composite_build_callback(self.build.id, initiate=False)

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
        self.assertTrue(isinstance(self.clf.clf.steps[1][1], SVC))
        self.assertEqual(self.clf.status, self.clf.FINISHED)
        self.assertIn('Finished training algorithm', self.clf.log)
        # LSVM
        self.clf.algorithm = Classifier.LSVM
        self.clf.status = self.clf.UNPROCESSED
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf, Pipeline))
        self.assertTrue(isinstance(self.clf.clf.steps[0][1], RobustScaler))
        self.assertTrue(isinstance(self.clf.clf.steps[1][1], LinearSVC))
        self.assertEqual(self.clf.status, self.clf.FINISHED)
        # Random Forest with custom composite set.
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
        self.clf.clf_args = '{"max_iter": 500}'
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf.steps[1][1], MLPClassifier))
        self.assertEqual(self.clf.status, self.clf.FINISHED)

        # Assert legend was created.
        self.assertEqual(self.clf.traininglayer.legend, {'0': 'Cloud free', '1': 'Shadow', '2': 'Cloud'})

        # Assert accuracy statistic has been calculated.
        self.assertNotEqual(self.clf.classifieraccuracy.accuracy_score, 0)

        # For regressor use cases, set the traininglayer to continuous.
        self.clf.traininglayer.continuous = True
        self.clf.collected_pixels.delete()
        self.clf.traininglayer.save()

        # SVR
        self.clf.algorithm = Classifier.SVR
        self.clf.status = self.clf.UNPROCESSED
        self.clf.clf_args = '{}'
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf, Pipeline))
        self.assertTrue(isinstance(self.clf.clf.steps[0][1], RobustScaler))
        self.assertTrue(isinstance(self.clf.clf.steps[1][1], SVR))
        self.assertEqual(self.clf.status, self.clf.FINISHED)
        # LSVR.
        self.clf.algorithm = Classifier.LSVR
        self.clf.status = self.clf.UNPROCESSED
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf, Pipeline))
        self.assertTrue(isinstance(self.clf.clf.steps[0][1], RobustScaler))
        self.assertTrue(isinstance(self.clf.clf.steps[1][1], LinearSVR))
        self.assertEqual(self.clf.status, self.clf.FINISHED)
        # Random Forest Regressor.
        self.clf.algorithm = Classifier.RFR
        self.clf.status = self.clf.UNPROCESSED
        self.clf.composite = self.composite
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf.steps[1][1], RandomForestRegressor))
        self.assertEqual(self.clf.status, self.clf.FINISHED)
        # Neural Network Regressor
        self.clf.algorithm = Classifier.NNR
        self.clf.status = self.clf.UNPROCESSED
        self.clf.composite = None
        self.clf.clf_args = '{"max_iter": 500}'
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf.steps[1][1], MLPRegressor))
        self.assertEqual(self.clf.status, self.clf.FINISHED)

        # Assert legend was created.
        self.assertIn('max', self.clf.traininglayer.legend)
        self.assertIn('std', self.clf.traininglayer.legend)

        # Assert rsquared was computed.
        self.assertNotEqual(self.clf.classifieraccuracy.rsquared, 0)

        # Error due to broken input data.
        self.cloud.pk = None
        self.cloud.value = 99
        self.cloud.save()
        self.clf.traininglayer.continuous = False
        self.clf.traininglayer.save()
        self.clf.algorithm = Classifier.RF
        self.clf.collected_pixels.delete()
        self.clf.clf_args = '{}'
        self.clf.save()
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
        # Test error if no aggregationlayer was specified.
        pred = PredictedLayer.objects.create(
            composite=self.composite,
            classifier=self.clf,
        )
        with self.assertRaisesMessage(ValueError, PREDICTION_CONFIG_ERROR_MSG):
            predict_sentinel_layer(pred.id)
        pred.refresh_from_db()
        self.assertIn('ERROR: {}'.format(PREDICTION_CONFIG_ERROR_MSG), pred.log)
        self.assertEqual(pred.status, PredictedLayer.FAILED)
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

    def test_keras_classifier(self):
        self._get_data()
        self.clf.algorithm = Classifier.KERAS
        self.clf.status = self.clf.UNPROCESSED
        model = Sequential()
        model.add(Dense(20, activation='relu'))
        model.add(Dropout(0.5))
        model.add(Dense(20, activation='relu'))
        model.add(Dropout(0.5))
        model.add(Dense(3, activation='softmax'))
        self.clf.keras_model_json = model.to_json()
        self.clf.clf_args = '''{
            "optimizer": "adagrad",
            "loss": "categorical_crossentropy",
            "metrics": ["accuracy"],
            "epochs": 10,
            "batch_size": 5
        }'''
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf, Pipeline))
        self.assertTrue(isinstance(self.clf.clf.steps[0][1], RobustScaler))
        self.assertTrue(isinstance(self.clf.clf.steps[1][1], KerasClassifier))
        self.assertEqual(self.clf.status, self.clf.FINISHED)
        self.assertIn('Finished training algorithm', self.clf.log)
        self.assertIn("Keras history:", self.clf.log)
        self.assertIn("Keras parameters:", self.clf.log)
        self.assertIn("{'batch_size': 5, 'epochs': 10", self.clf.log)
        # Test prediction.
        pred = PredictedLayer.objects.create(
            composite=self.composite,
            classifier=self.clf,
            aggregationlayer=self.agglayer,
        )
        predict_sentinel_layer(pred.id)
        pred.refresh_from_db()
        # Tiles have been created.
        self.assertTrue(pred.rasterlayer.rastertile_set.count() > 0)

    def test_keras_classifier_time(self):
        self._get_data()
        composite_build_callback(self.build2.id, initiate=True, rebuild=True)
        composite_build_callback(self.build2.id, initiate=False)
        self.clf.algorithm = Classifier.KERAS
        self.clf.status = self.clf.UNPROCESSED
        # expected input data shape: (batch_size, timesteps, data_dim)
        model = Sequential()
        model.add(GRU(32, return_sequences=True, return_state=False))  # returns a sequence of vectors of dimension 32
        model.add(BatchNormalization())
        model.add(GRU(32, return_sequences=True))  # returns a sequence of vectors of dimension 32
        model.add(BatchNormalization())
        model.add(GRU(32))  # return a single vector of dimension 32
        model.add(BatchNormalization())
        model.add(Dense(3, activation='softmax'))
        self.clf.keras_model_json = model.to_json()
        self.clf.clf_args = '''{
            "optimizer": "rmsprop",
            "loss": "categorical_crossentropy",
            "metrics": ["accuracy"],
            "epochs": 10,
            "batch_size": 5
        }'''
        self.clf.save()
        self.clf.composites.add(self.composite)
        self.clf.composites.add(self.composite2)
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf, Pipeline))
        self.assertTrue(isinstance(self.clf.clf.steps[0][1], RNNRobustScaler))
        self.assertTrue(isinstance(self.clf.clf.steps[1][1], KerasClassifier))
        self.assertEqual(self.clf.status, self.clf.FINISHED)
        self.assertIn('Finished training algorithm', self.clf.log)
        # Test prediction.
        pred = PredictedLayer.objects.create(
            classifier=self.clf,
            aggregationlayer=self.agglayer,
        )
        predict_sentinel_layer(pred.id)
        pred.refresh_from_db()
        # Tiles have been created.
        self.assertTrue(pred.rasterlayer.rastertile_set.count() > 0)

    def test_training_inconsistent_configuration(self):
        self.clf.algorithm = Classifier.NNR
        self.clf.save()
        self.clf.traininglayer.continuous = False
        self.clf.traininglayer.save()
        train_sentinel_classifier(self.clf.id)
        self.clf.refresh_from_db()
        self.assertEqual(self.clf.status, Classifier.FAILED)
        self.assertIn('Regressors require continuous input datasets.', self.clf.log)
        self.clf.algorithm = Classifier.NN
        self.clf.save()
        self.clf.traininglayer.continuous = True
        self.clf.traininglayer.save()
        train_sentinel_classifier(self.clf.id)
        self.clf.refresh_from_db()
        self.assertEqual(self.clf.status, Classifier.FAILED)
        self.assertIn('Classifiers require discrete input datasets.', self.clf.log)

    def test_training_export(self):
        self._get_data()
        # Get rasterlayer id.
        band_names = ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B8A', 'RL{}'.format(self.composite.compositeband_set.first().rasterlayer_id)]
        band_names = ','.join(band_names)
        # Create export task.
        exp = TrainingLayerExport.objects.create(traininglayer=self.clf.traininglayer)
        # Run export task.
        export_training_data(exp.id, band_names)
        # Check export file has been created.
        exp.refresh_from_db()
        dat = exp.data.read()
        self.assertTrue(len(dat) > 500)

        exp = TrainingLayerExport.objects.create(traininglayer=self.clf.traininglayer)
        self.clf.traininglayer.continuous = True
        self.clf.traininglayer.save()
        # Run export task.
        export_training_data(exp.id, band_names)
        # Check export file has been created.
        exp.refresh_from_db()
        dat = exp.data.read()
        self.assertTrue(len(dat) > 500)

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
        self.clf.traininglayer.continuous = False
        self.clf.traininglayer.save()
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
        self.assertGreater(data['results'][0]['classifieraccuracy']['accuracy_score'], 0)

    def test_classifier_training_from_preloaded_pixels(self):
        self._get_data()
        # SVM
        self.clf.algorithm = Classifier.SVM
        self.clf.status = self.clf.UNPROCESSED
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        dat = self.clf.collected_pixels.read()
        self.assertTrue(len(dat) > 0)
        self.clf.status = self.clf.UNPROCESSED
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertIn('Loaded from file', self.clf.log)
        loaded = numpy.load(self.clf.collected_pixels)
        X = loaded['X']
        Y = loaded['Y']
        PID = loaded['PID']
        self.assertTrue(Y.shape[0] > 0)
        self.assertEqual(Y.shape[0], X.shape[0])
        self.assertEqual(Y.shape[0], PID.shape[0])
