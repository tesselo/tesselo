import datetime
import os
import shutil
import tempfile
from unittest.mock import patch

import dateutil
import numpy
from keras.layers import GRU, BatchNormalization, Dense, Dropout
from keras.models import Model, Sequential
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

from classify.const import (
    KERAS_JSON_MALFORMED_ERROR_MSG, KERAS_LAST_LAYER_NOT_DENSE_ERROR_MSG, KERAS_LAST_LAYER_UNITS_ERROR_MSG_TMPL,
    KERAS_MIN_ONE_LAYER_ERROR_MSG, PREDICTION_CONFIG_ERROR_MSG, TP_MSG_NON_KERAS, TP_MSG_NOT_FINISHED,
    TP_MSG_REGRESSOR, VALUE_CONFIG_ERROR_MSG
)
from classify.models import (
    Classifier, PredictedLayer, PredictedLayerChunk, TrainingLayer, TrainingPixels, TrainingPixelsPatch,
    TrainingSample
)
from classify.tasks import predict_sentinel_layer, train_sentinel_classifier
from classify.utils import RNNRobustScaler
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.gis.gdal import OGRGeometry
from django.test import TestCase, override_settings
from django.urls import reverse
from jobs import ecs
from sentinel.models import Composite, MGRSTile, SentinelTile


@patch('sentinel.tasks.boto3.session.botocore.paginate.PageIterator.search', iterator_search)
@patch('sentinel.tasks.boto3.session.Session.client', client_get_object)
@patch('raster.tiles.parser.urlretrieve', point_to_test_file)
@patch('sentinel.tasks.get_raster_tile', patch_get_raster_tile)
@patch('sentinel.tasks.write_raster_tile', patch_write_raster_tile)
@patch('classify.tasks.get_raster_tile', patch_get_raster_tile)
@patch('classify.tasks.write_raster_tile', patch_write_raster_tile)
@patch('jobs.ecs.process_l2a', patch_process_l2a)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, LOCAL=True)
class SentinelClassifierTest(TestCase):

    @classmethod
    def setUpClass(cls):

        super().setUpClass()

        mocks = [
            patch('sentinel.tasks.boto3.session.botocore.paginate.PageIterator.search', iterator_search),
            patch('sentinel.tasks.boto3.session.Session.client', client_get_object),
            patch('raster.tiles.parser.urlretrieve', point_to_test_file),
            patch('sentinel.tasks.get_raster_tile', patch_get_raster_tile),
            patch('sentinel.tasks.write_raster_tile', patch_write_raster_tile),
            patch('classify.tasks.get_raster_tile', patch_get_raster_tile),
            patch('classify.tasks.write_raster_tile', patch_write_raster_tile),
            patch('classify.collectpixels.get_raster_tile', patch_get_raster_tile),
            patch('jobs.ecs.process_l2a', patch_process_l2a),
        ]
        for mock in mocks:
            mock.start()

        settings.MEDIA_ROOT = tempfile.mkdtemp()

        bbox = [11833687.0, -469452.0, 11859687.0, -441452.0]
        bbox = OGRGeometry.from_bbox(bbox)
        bbox.srid = 3857
        cls.agglayer = AggregationLayer.objects.create(name='Test Agg Layer')
        cls.zone = AggregationArea.objects.create(
            name='Test Agg Area',
            aggregationlayer=cls.agglayer,
            geom='SRID=3857;MULTIPOLYGON((( 11833687.0 -469452.0, 11833787.0 -469452.0, 11833787.0 -469352.0, 11833687.0 -469352.0, 11833687.0 -469452.0)))'
        )
        cls.composite = Composite.objects.create(
            name='The World',
            min_date='2015-12-01',
            max_date='2015-12-31',
        )
        cls.composite2 = Composite.objects.create(
            name='The World 2',
            min_date='2015-10-01',
            max_date='2015-10-31',
        )
        cls.composite3 = Composite.objects.create(
            name='The World 2',
            min_date='2015-11-01',
            max_date='2015-11-30',
        )

        cls.traininglayer = TrainingLayer.objects.create(name='Test Training Layer')

        counter = 0
        STEP_SIZE = 25
        for i in range(5):
            for index, name in enumerate(['Cloud', 'Shadow', 'Cloud free']):
                dat = [
                    11844687 + STEP_SIZE * counter,
                    -459865 + STEP_SIZE * counter,
                    11844687 + STEP_SIZE * (counter + 1),
                    -459865 + STEP_SIZE * counter,
                    11844687 + STEP_SIZE * (counter + 1),
                    -459865 + STEP_SIZE * (counter + 1),
                    11844687 + STEP_SIZE * counter,
                    -459865 + STEP_SIZE * (counter + 1),
                    11844687 + STEP_SIZE * counter,
                    -459865 + STEP_SIZE * counter,
                ]
                TrainingSample.objects.create(
                    geom='SRID=3857;POLYGON(({} {}, {} {}, {} {}, {} {}, {} {}))'.format(*dat),
                    category=name,
                    value=index + 1,
                    traininglayer=cls.traininglayer,
                    composite=cls.composite,
                    date='2015-{}-1{}'.format(numpy.random.choice([10, 11], 1)[0], i),
                )
                counter += 1

        cls.clf = Classifier.objects.create(
            name='Clouds',
            algorithm=Classifier.RF,
            traininglayer=cls.traininglayer,
            splitfraction=0.2,
            training_all_touched=False,
        )

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        try:
            shutil.rmtree(settings.MEDIA_ROOT)
        except:
            pass

    def _get_files(self, path):
        files = []
        for root, subdirs, files in os.walk(os.path.join(settings.MEDIA_ROOT, path)):
            files += files
        return files

    def test_training_pixels_collection_and_classifier_training(self):
        # Create trainingpixels object.
        tr = TrainingPixels.objects.create(
            name='abc',
            band_names='B03,B04',
            traininglayer=self.traininglayer,
            buffer=0,
        )
        tr.composites.add(self.composite)
        tr.composites.add(self.composite2)
        tr.composites.add(self.composite3)
        # Populate pixels.
        ecs.populate_trainingpixels(tr.id)
        tr.refresh_from_db()
        # The pixels are as expected.
        self.assertEqual(tr.trainingpixelspatch_set.count(), 1)
        self.assertEqual(tr.trainingpixelspatch_set.first().status, TrainingPixelsPatch.FINISHED)
        self.assertEqual(tr.status, TrainingPixels.FINISHED)
        X, Y, PID, SID, categories = tr.unpack_collected_pixels()
        self.assertDictEqual(categories, {'Cloud': 1, 'Shadow': 2, 'Cloud free': 3})
        self.assertEqual(X.shape, (196, 3, 2))
        self.assertEqual(Y.shape, (196, ))
        self.assertEqual(PID.shape, (196, ))
        self.assertEqual(PID.shape, (196, ))
        # Train a classifier based on trainingpixels.
        self.clf.algorithm = Classifier.KERAS
        self.clf.status = self.clf.UNPROCESSED
        self.clf.trainingpixels = tr
        self.clf.wrap_keras_with_sklearn = False
        model = Sequential()
        model.add(GRU(32))
        model.add(BatchNormalization())
        model.add(Dense(3, activation='softmax'))
        self.clf.keras_model_json = model.to_json()
        self.clf.clf_args = '''{
            "optimizer": "rmsprop",
            "loss": "categorical_crossentropy",
            "metrics": ["accuracy"],
            "epochs": 3,
            "batch_size": 50,
            "verbose": 0
        }'''
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf.refresh_from_db()
        # Classifier training on pixels was successful.
        self.assertEqual(self.clf.status, self.clf.FINISHED)
        self.assertTrue(isinstance(self.clf.clf, Model))

    def test_training_pixels_collection_and_classifier_training_misconfiguration(self):
        # Create trainingpixels object.
        tr = TrainingPixels.objects.create(
            name='abc',
            band_names='B03,B04',
            traininglayer=self.traininglayer,
            buffer=0,
        )
        # Train a classifier based on trainingpixels.
        self.clf.algorithm = Classifier.KERAS
        self.clf.wrap_keras_with_sklearn = False
        self.clf.status = self.clf.UNPROCESSED
        self.clf.trainingpixels = tr
        self.clf.save()
        # Pixels were not yet collected.
        train_sentinel_classifier(self.clf.id)
        self.clf.refresh_from_db()
        self.assertEqual(self.clf.status, self.clf.FAILED)
        self.assertIn(TP_MSG_NOT_FINISHED, self.clf.log)
        # Algorithm is not keras.
        self.clf.algorithm = Classifier.RF
        self.clf.status = self.clf.UNPROCESSED
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf.refresh_from_db()
        self.assertEqual(self.clf.status, self.clf.FAILED)
        self.assertIn(TP_MSG_NON_KERAS, self.clf.log)
        # Algorithm is a regressor.
        self.clf.traininglayer.continuous = True
        self.clf.traininglayer.save()
        self.clf.algorithm = Classifier.KERAS_REGRESSOR
        self.clf.status = self.clf.UNPROCESSED
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf.refresh_from_db()
        self.assertEqual(self.clf.status, self.clf.FAILED)
        self.assertIn(TP_MSG_REGRESSOR, self.clf.log)

    def test_training_pixels_collection_buffer(self):
        tr = TrainingPixels.objects.create(
            name='abc',
            band_names='B03,B04,B08,B09',
            traininglayer=self.traininglayer,
            buffer=50,
        )
        tr.composites.add(self.composite)
        tr.composites.add(self.composite2)
        tr.composites.add(self.composite3)
        ecs.populate_trainingpixels(tr.id)
        tr.refresh_from_db()
        X, Y, PID, SID, categories = tr.unpack_collected_pixels()
        self.assertEqual(X.shape, (2625, 3, 4))

    def test_classifier_training(self):
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
        self.assertEqual(self.clf.traininglayer.legend, {'1': 'Cloud', '2': 'Shadow', '3': 'Cloud free'})

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
        sample = TrainingSample.objects.first()
        sample.value = 99
        sample.save()
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

    def test_classifier_prediction_composite_aggregationlayer(self):
        train_sentinel_classifier(self.clf.id)
        # Test error if no aggregationlayer was specified.
        pred = PredictedLayer.objects.create(
            classifier=self.clf,
        )
        pred.composites.add(self.composite)
        with self.assertRaisesMessage(ValueError, PREDICTION_CONFIG_ERROR_MSG):
            predict_sentinel_layer(pred.id)
        pred.refresh_from_db()
        self.assertIn('ERROR: {}'.format(PREDICTION_CONFIG_ERROR_MSG), pred.log)
        self.assertEqual(pred.status, PredictedLayer.FAILED)
        # Test with aggregationlayer argument.
        pred = PredictedLayer.objects.create(
            aggregationlayer=self.agglayer,
            classifier=self.clf,
        )
        pred.composites.add(self.composite)
        predict_sentinel_layer(pred.id)
        pred.refresh_from_db()
        # Tiles have been created.
        files = self._get_files('tiles/{}/14'.format(pred.rasterlayer_id))
        self.assertTrue(len(files), 1)
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
        self.clf.algorithm = Classifier.KERAS
        self.clf.wrap_keras_with_sklearn = False
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
            "batch_size": 5,
            "verbose": 0
        }'''
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf, Model))
        self.assertEqual(self.clf.status, self.clf.FINISHED)
        self.assertIn('Finished training algorithm', self.clf.log)
        self.assertIn("Keras history:", self.clf.log)
        self.assertIn("Keras parameters:", self.clf.log)
        self.assertIn("{'batch_size': 5, 'epochs': 10", self.clf.log)
        # Test prediction.
        pred = PredictedLayer.objects.create(
            classifier=self.clf,
            aggregationlayer=self.agglayer,
        )
        pred.composites.add(self.composite)
        predict_sentinel_layer(pred.id)
        pred.refresh_from_db()
        # Tiles have been created.
        files = self._get_files('tiles/{}/14'.format(pred.rasterlayer_id))
        self.assertTrue(len(files), 1)

    def test_keras_regressor(self):
        # For regressor use cases, set the traininglayer to continuous.
        self.clf.traininglayer.continuous = True
        self.clf.traininglayer.save()
        # Regressor setup.
        self.clf.algorithm = Classifier.KERAS_REGRESSOR
        self.clf.status = self.clf.UNPROCESSED
        self.clf.wrap_keras_with_sklearn = False
        model = Sequential()
        model.add(Dense(20, activation='relu'))
        model.add(Dropout(0.5))
        model.add(Dense(20, activation='relu'))
        model.add(Dropout(0.5))
        model.add(Dense(1, activation='linear'))
        self.clf.keras_model_json = model.to_json()
        self.clf.clf_args = '''{
            "optimizer": "adagrad",
            "loss": "mse",
            "metrics": ["mean_squared_error"],
            "epochs": 10,
            "batch_size": 5,
            "verbose": 0
        }'''
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf = Classifier.objects.get(id=self.clf.id)
        self.assertTrue(isinstance(self.clf.clf, Model))
        self.assertEqual(self.clf.status, self.clf.FINISHED)
        self.assertIn('Finished training algorithm', self.clf.log)
        self.assertIn("Keras history:", self.clf.log)
        self.assertIn("Keras parameters:", self.clf.log)
        self.assertIn("{'batch_size': 5, 'epochs': 10", self.clf.log)
        self.assertNotEqual(self.clf.classifieraccuracy.rsquared, 0)

        # Test prediction.
        pred = PredictedLayer.objects.create(
            classifier=self.clf,
            aggregationlayer=self.agglayer,
        )
        pred.composites.add(self.composite)
        predict_sentinel_layer(pred.id)
        pred.refresh_from_db()
        # Tiles have been created.
        files = self._get_files('tiles/{}/14'.format(pred.rasterlayer_id))
        self.assertTrue(len(files), 1)

    def test_keras_classifier_time(self):
        self.clf.algorithm = Classifier.KERAS
        self.clf.wrap_keras_with_sklearn = False
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
            "epochs": 3,
            "batch_size": 50,
            "verbose": 0
        }'''
        self.clf.save()

        # Associate composites to classifier.
        self.clf.composites.add(self.composite)
        self.clf.composites.add(self.composite2)
        self.clf.composites.add(self.composite3)

        # Test the look back feature.
        self.clf.look_back_steps = 2
        self.clf.splitfraction = 0.35
        self.clf.split_random_seed = 23
        self.clf.split_by_polygon = True
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf.refresh_from_db()
        self.assertIn('Finished training algorithm', self.clf.log)
        self.assertEqual(Classifier.FINISHED, self.clf.status)

        # Reset look back feature and clasifier.
        self.clf.collected_pixels.delete()
        self.clf.look_back_steps = 0
        self.clf.split_by_polygon = False
        self.clf.log = ''
        self.clf.status = self.clf.UNPROCESSED
        self.clf.wrap_keras_with_sklearn = True
        self.clf.save()

        # Train classifier in full archive mode.
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
        files = self._get_files('tiles/{}/14'.format(pred.rasterlayer_id))
        self.assertTrue(len(files), 1)

        # Test wrong configuration errors.
        self.clf.keras_model_json = '{"this": "is not a keras model json"}'
        self.clf.log = ''
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf.refresh_from_db()
        self.assertIn(KERAS_JSON_MALFORMED_ERROR_MSG, self.clf.log)
        self.assertEqual(self.clf.status, Classifier.FAILED)

        # No-layers model.
        error_model = Sequential()
        self.clf.keras_model_json = error_model.to_json()
        self.clf.log = ''
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf.refresh_from_db()
        self.assertIn(KERAS_MIN_ONE_LAYER_ERROR_MSG, self.clf.log)
        self.assertEqual(self.clf.status, Classifier.FAILED)

        # Last not dense error.
        error_model = Sequential()
        error_model.add(GRU(32, return_sequences=True, return_state=False))
        self.clf.keras_model_json = error_model.to_json()
        self.clf.log = ''
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf.refresh_from_db()
        self.assertIn(KERAS_LAST_LAYER_NOT_DENSE_ERROR_MSG, self.clf.log)
        self.assertEqual(self.clf.status, Classifier.FAILED)

        # Replace last layer with a broken one, where the number of nodes is 2,
        # and the correct nr of nodes is 3.
        model.layers.pop()  # Remove last layer.
        model.add(Dense(2, activation='softmax'))
        self.clf.keras_model_json = model.to_json()
        self.clf.log = ''
        self.clf.save()
        train_sentinel_classifier(self.clf.id)
        self.clf.refresh_from_db()
        self.assertIn(
            KERAS_LAST_LAYER_UNITS_ERROR_MSG_TMPL.format(2, 3),
            self.clf.log,
        )

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

    def test_classifier_report_and_list_views(self):
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
        self.assertIn('loading from file', self.clf.log)
        loaded = numpy.load(self.clf.collected_pixels)
        X = loaded['X']
        Y = loaded['Y']
        PID = loaded['PID']
        self.assertTrue(Y.shape[0] > 0)
        self.assertEqual(Y.shape[0], X.shape[0])
        self.assertEqual(Y.shape[0], PID.shape[0])

    def test_predictedlayer_min_max_date_signal(self):
        pred = PredictedLayer.objects.create()
        pred.composites.set([self.composite, self.composite2, self.composite3])
        pred.refresh_from_db()
        self.assertEqual(pred.min_date, datetime.date(2015, 10, 1))
        self.assertEqual(pred.max_date, datetime.date(2015, 12, 31))

        stile_date = datetime.date(2015, 3, 23)
        # Set up sentineltile.
        mgrstile = MGRSTile.objects.create(utm_zone='AA', latitude_band='2', grid_square='AA')
        stile = SentinelTile.objects.create(
            prefix='test',
            datastrip='test',
            product_name='test',
            mgrstile=mgrstile,
            collected=dateutil.parser.parse("2015-03-23T19:04:17.320Z"),
            cloudy_pixel_percentage=0.95,
            data_coverage_percentage=100,
        )
        pred = PredictedLayer.objects.create(sentineltile=stile)
        pred.refresh_from_db()
        self.assertEqual(pred.min_date, stile_date)
        self.assertEqual(pred.max_date, stile_date)
