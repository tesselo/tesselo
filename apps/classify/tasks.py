import importlib
import io
import pickle
import zipfile
from tempfile import TemporaryFile

import h5py
import numpy
import sentry_sdk
from django.contrib.gis.db.models import Extent
from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos import Polygon
from django.core.files import File
from raster.rasterize import rasterize
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import tile_bounds, tile_index_range
from rasterio.features import sieve
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler
from tensorflow.config import list_physical_devices
from tensorflow.keras.layers import Dense
from tensorflow.keras.models import model_from_json
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.wrappers.scikit_learn import KerasClassifier

from classify.const import (
    CLASSIFICATION_DATATYPE, CLASSIFICATION_DATATYPE_GDAL, CLASSIFICATION_NODATA, FITTING_ERROR_MSG, KERAS_FIT_ARGS,
    KERAS_JSON_MALFORMED_ERROR_MSG, KERAS_LAST_LAYER_NOT_DENSE_ERROR_MSG, KERAS_LAST_LAYER_UNITS_ERROR_MSG_TMPL,
    KERAS_MIN_ONE_LAYER_ERROR_MSG, KERAS_TRAIN_TYPE, PIPELINE_ESTIMATOR_NAME, PIPELINE_SCALER_NAME,
    PREDICTION_CONFIG_ERROR_MSG, REGRESSION_DATATYPE, REGRESSION_DATATYPE_GDAL, SCALE, SENTINEL_PIXELTYPE,
    SIEVE_CONIFG_ERROR_MSG, TP_MSG_NOT_FINISHED, TP_MSG_REGRESSOR, TRAINING_DATA_SPLIT_ERROR_MSG,
    VALUE_CONFIG_ERROR_MSG, ZIP_ESTIMATOR_NAME, ZIP_PIPELINE_NAME, ZOOM
)
from classify.models import Classifier, ClassifierAccuracy, PredictedLayer, PredictedLayerChunk, TrainingPixels
from classify.utils import LogCallback, PixelSequence, RNNRobustScaler
from jobs import ecs
from report.tasks import push_reports
from sentinel.const import SENTINEL_NODATA_VALUE
from sentinel.utils import aggregate_tile, get_raster_tile, write_raster_tile
from sentinel_1.const import POLARIZATION_DV_BANDS


def get_classifier_data(rasterlayer_ids, tilez, tilex, tiley):
    """
    Builds the 13 band training tile file for a training tile instance.
    """
    # Get data for a tile of this scene.
    result = []
    for layer_id in rasterlayer_ids:
        tile = get_raster_tile(layer_id, tilez=tilez, tilex=tilex, tiley=tiley)
        if not tile:
            return
        result.append(tile.bands[0].data().ravel())

    return numpy.array(result).T


def get_rasterlayer_ids(band_names, rasterlayer_lookup):
    """
    Compile ordered list of rasterlayer ids to include in training or prediction.
    """
    # Compile a list of rasterlayer ids (order matters here).
    rasterlayer_ids = []
    for band in band_names:

        if band.lower().startswith('rl'):
            # If the band name starts with RL, assume its a rasterlayer id.
            # RL23 would be raster layer id 23.
            rasterlayer_ids.append(int(band[2:]))
        elif band.lower().startswith('b'):
            # Otherwise get the band rasterlayer id from the rasterlayer lookup.
            rasterlayer_ids.append(rasterlayer_lookup.get(band + '.jp2'))
        elif band.lower() in [dat.lower() for dat in POLARIZATION_DV_BANDS]:
            rasterlayer_ids.append(rasterlayer_lookup.get(band))
        else:
            raise ValueError('Band names have to be similar to either B01 or RL23.')

    return rasterlayer_ids


def populate_training_matrix_sample(sample, is_regressor, categories, rasterlayer_lookup, target_type, all_touched, band_names):
    X = numpy.empty(shape=(0, len(band_names)), dtype=SENTINEL_PIXELTYPE)
    Y = numpy.empty(shape=(0, ), dtype=target_type)
    # Track pixel IDs to allow merging different training matrices from
    # different traininglayers.
    PID = numpy.empty(shape=(0, ), dtype='int64')
    SID = numpy.empty(shape=(0, ), dtype='int64')
    # Check for consistency in training samples for dicrete datasets.
    if not is_regressor:
        if sample.category in categories:
            if sample.value != categories[sample.category]:
                raise ValueError(VALUE_CONFIG_ERROR_MSG)
        else:
            categories[sample.category] = sample.value if is_regressor else int(sample.value)
    # Take rasterlayer lookup from the trainingsample if it was not provided as
    # input.
    if rasterlayer_lookup:
        rasterlayer_lookup_sample = rasterlayer_lookup
    elif sample.composite:
        rasterlayer_lookup_sample = sample.composite.rasterlayer_lookup
    else:
        rasterlayer_lookup_sample = sample.sentineltile.rasterlayer_lookup
    # Convert lookup to id list.
    rasterlayer_ids = get_rasterlayer_ids(band_names, rasterlayer_lookup_sample)
    # Loop over index range for tiles intersecting with the sample geom.
    idx = tile_index_range(sample.geom.transform(3857, clone=True).extent, ZOOM)
    for tilex in range(idx[0], idx[2] + 1):
        for tiley in range(idx[1], idx[3] + 1):
            # Get stacked tile data for this tile.
            data = get_classifier_data(rasterlayer_ids, ZOOM, tilex, tiley)
            if data is None:
                continue
            # Create a target raster for the rasterization.
            bounds = tile_bounds(tilex, tiley, ZOOM)
            rast = GDALRaster(
                {
                    'width': WEB_MERCATOR_TILESIZE,
                    'height': WEB_MERCATOR_TILESIZE,
                    'srid': WEB_MERCATOR_SRID,
                    'scale': [SCALE, -SCALE],
                    'origin': [bounds[0], bounds[3]],
                    'datatype': 1,
                    'nr_of_bands': 1,
                }
            )
            # Rasterize the sample area.
            sample_rast = rasterize(sample.geom, rast, all_touched=all_touched)
            # Create a selector boolean array from rasterized geometry.
            sample_pixels = sample_rast.bands[0].data().ravel()
            selector = sample_pixels == 1
            # Create a constant array with sample value for all intersecting pixels.
            sample_values = (sample.value * numpy.ones(sum(selector))).astype(target_type)
            # Add sample values to dependent variable.
            Y = numpy.hstack([sample_values, Y])
            # Use selector to pick sample pixels over geom.
            data = data[selector]
            # Add explanatory variables to stack.
            X = numpy.vstack([data, X])
            # Compute pixel ids for this tile.
            pid_from = (tiley * (2 ** ZOOM) + tilex) * WEB_MERCATOR_TILESIZE ** 2
            pid_to = pid_from + WEB_MERCATOR_TILESIZE ** 2
            pids = numpy.arange(pid_from, pid_to)
            PID = numpy.hstack([pids[selector], PID])
            # Make array with sample id for separating validation pixels at
            # training sample level (instead of pixel level).
            sample_id_values = (sample.id * numpy.ones(sum(selector))).astype('int64')
            SID = numpy.hstack([sample_id_values, SID])

    return X, Y, PID, SID, categories


def populate_training_matrix(traininglayer, band_names, rasterlayer_lookup=None, is_regressor=False, all_touched=True):
    # Determine sample value datatype.
    target_type = REGRESSION_DATATYPE if is_regressor else CLASSIFICATION_DATATYPE
    # Create numpy arrays holding training data.
    number_of_bands = len(band_names)
    X = numpy.empty(shape=(0, number_of_bands), dtype=SENTINEL_PIXELTYPE)
    Y = numpy.empty(shape=(0, ), dtype=target_type)
    # Track pixel IDs to allow merging different training matrices from
    # different traininglayers.
    PID = numpy.empty(shape=(0, ), dtype='int64')
    SID = numpy.empty(shape=(0, ), dtype='int64')
    # Dictionary for categories or statistics.
    categories = {}
    # Loop through training tiles to build training set.
    for sample in traininglayer.trainingsample_set.all():
        Xh, Yh, PIDh, SIDh, categories = populate_training_matrix_sample(
            sample,
            is_regressor,
            categories,
            rasterlayer_lookup,
            target_type,
            all_touched,
            band_names,
        )
        # Add sample values to dependent variable.
        Y = numpy.hstack([Yh, Y])
        # Add explanatory variables to stack.
        X = numpy.vstack([Xh, X])
        # Add pixel ids for this tile to stack.
        PID = numpy.hstack([PIDh, PID])
        # Add sample IDs to stack.
        SID = numpy.hstack([SIDh, SID])

    save_traininglayer_legend(traininglayer, categories, Y, is_regressor)

    return X, Y, PID, SID


def save_traininglayer_legend(traininglayer, categories, Y, is_regressor):
    """
    Update traininglayer legend using categories from training matrix collection.
    """
    if is_regressor:
        # For continuous values, track statistics instead of a legend.
        traininglayer.legend = {
            'min': numpy.min(Y),
            'max': numpy.max(Y),
            'std': numpy.std(Y),
            'avg': numpy.average(Y),
        }
    else:
        # For discrete values, store the category lookup.
        traininglayer.legend = {str(int(val)): key for key, val in categories.items()}

    traininglayer.save()


def get_keras_model(keras_model_json, optimizer, loss=None, metrics=None, loss_weights=None, sample_weight_mode=None, weighted_metrics=None, target_tensors=None):
    """
    Wrap Keras model to scikit learn api.
    """
    clf = model_from_json(keras_model_json)
    clf.compile(
        optimizer, loss=loss, metrics=metrics, loss_weights=loss_weights,
        sample_weight_mode=sample_weight_mode, weighted_metrics=weighted_metrics,
        target_tensors=target_tensors
    )
    return clf


def populate_training_matrix_time(classifier):
    Xs = None
    Ys = None
    PIDs = None
    SIDs = None
    # Dictionary for categories or statistics.
    categories = {}
    # Determine sample value datatype.
    target_type = REGRESSION_DATATYPE if classifier.is_regressor else CLASSIFICATION_DATATYPE
    # Get all classifier composites.
    composites = classifier.composites.all().order_by('min_date')
    for index, sample in enumerate(classifier.traininglayer.trainingsample_set.all()):
        if index % 250 == 0 and index > 0:
            classifier.write('Collected data for {} training samples.'.format(index))
        # Check if all composites should be included in training (fixed end
        # date for all samples) or a flexible selection shall be used based on
        # the sample date stamp.
        if classifier.look_back_steps > 0:
            # Get first composite after the min date.
            try:
                composite_after = composites.filter(min_date__gte=sample.date)[0]
            except IndexError as e:
                sentry_sdk.capture_exception(e)
                classifier.write('Skipping sample ID {}. Failed finding composites after sample date {}.'.format(sample.id, sample.date))
                continue
            # Select the last N steps before the.
            if classifier.look_back_steps > 1:
                composites_before = composites.order_by('-min_date').exclude(min_date__gte=sample.date)[:(classifier.look_back_steps - 1)]
                if len(composites_before) != classifier.look_back_steps - 1:
                    msg = 'Skipping sample ID {}. Failed finding {} composites before date {}, only found {} composites.'.format(
                        sample.id,
                        classifier.look_back_steps - 1,
                        sample.date,
                        len(composites_before),
                    )
                    classifier.write(msg)
                    continue
                composites_before = reversed(list(composites_before))
            else:
                composites_before = []
            # Combine the "last after date" and "N before date" composite lists.
            sample_composites = list(composites_before) + [composite_after]
        else:
            # Select all available composites.
            sample_composites = composites

        for composite in sample_composites:
            try:
                X, Y, PID, SID, categories = populate_training_matrix_sample(
                    sample,
                    classifier.is_regressor,
                    categories,
                    composite.rasterlayer_lookup,
                    target_type,
                    classifier.training_all_touched,
                    classifier.band_names.split(','),
                )
            except ValueError:
                classifier.write(VALUE_CONFIG_ERROR_MSG, classifier.FAILED)
                raise

            if Xs is None:
                Xs = X
                Ys = Y
                PIDs = PID
                SIDs = SID
            else:
                Ys = numpy.hstack([Ys, Y])
                Xs = numpy.vstack([Xs, X])
                PIDs = numpy.hstack([PIDs, PID])
                SIDs = numpy.hstack([SIDs, SID])

    # Combine data
    all_data = numpy.vstack([PIDs, SIDs, Ys, Xs.T]).T
    # Sort by PID and SID
    all_data = all_data[numpy.lexsort((PIDs, SIDs))]
    # Count number of unique pixel IDs (PIDs) over each sample (SIDs).
    nr_of_observations = len(Ys) / len(sample_composites)
    # Split into groups by unique pixel/sampmle combos to convert data into
    # keras ready tensor shapes.
    try:
        all_data = numpy.array(numpy.vsplit(all_data, nr_of_observations))
    except ValueError:
        classifier.write(TRAINING_DATA_SPLIT_ERROR_MSG, classifier.FAILED)
        raise

    # Extract and return individual arrays.
    PIDs = all_data[:, 0, 0]
    SIDs = all_data[:, 0, 1]
    Ys = all_data[:, 0, 2]
    Xs = all_data[:, :, 3:]

    save_traininglayer_legend(classifier.traininglayer, categories, Ys, classifier.is_regressor)

    return Xs, Ys, PIDs, SIDs


def train_sentinel_classifier(classifier_id):
    """
    Trains a classifier based on the registered tiles and sample data.
    """
    # Get classifier model.
    classifier = Classifier.objects.get(pk=classifier_id)

    # Make consistency checks.
    if classifier.is_regressor and not classifier.traininglayer.continuous:
        classifier.write('Regressors require continuous input datasets.', classifier.FAILED)
        return
    elif not classifier.is_regressor and classifier.traininglayer.continuous:
        classifier.write('Classifiers require discrete input datasets.', classifier.FAILED)
        return
    elif classifier.look_back_steps > 0 and classifier.composites.count() < (classifier.look_back_steps):
        classifier.write('Wrong look back configuration. Specify at least {} composites to look back to, found only {}.'.format(classifier.look_back_steps, classifier.composites.count()))
    else:
        method = 'single layer'
        if classifier.look_back_steps > 0:
            method = 'limited look back'
        elif classifier.composites.count():
            method = 'all available composites'
        classifier.write('Started collecting training data with {} input method'.format(method), classifier.PROCESSING)
    if classifier.auto_class_weights:
        if not classifier.is_keras:
            classifier.write('Classifiers auto class weights are only for keras models. Set "auto_class_weights" to False for non-keras models.', classifier.FAILED)
            return
        if classifier.is_regressor:
            classifier.write('Classifiers auto class weights are only for classifications. Set "auto_class_weights" to False for regressors.', classifier.FAILED)
            return

    # Remove current accuracy matrix.
    if hasattr(classifier, 'classifieraccuracy'):
        classifier.classifieraccuracy.delete()

    # Check if pixels have already been collected.
    if classifier.trainingpixels_id:
        # Sanity checks.
        if classifier.is_regressor:
            classifier.write(TP_MSG_REGRESSOR, classifier.FAILED)
            return
        if classifier.trainingpixels.status != TrainingPixels.FINISHED:
            classifier.write(TP_MSG_NOT_FINISHED, classifier.FAILED)
            return
        # Get pixels from trainingpixels object.
        classifier.write('Found a trainingpixels object, loading from packed pixels.')
        X, Y, PID, SID, categories = classifier.trainingpixels.unpack_collected_pixels()
        # Flatten the time dimension for non-keras models.
        if not classifier.is_keras and len(X.shape) == 3:
            X = X.reshape((X.shape[0], X.shape[1] * X.shape[2]))
    elif classifier.collected_pixels.name:
        classifier.write('Found existing collected training data, loading from file.')
        loaded = numpy.load(classifier.collected_pixels)
        X = loaded['X']
        Y = loaded['Y']
        PID = loaded['PID']
        SID = loaded['SID']
    else:
        classifier.write('Collecting pixels from composites data.')
        # Check if the classifier has a custom data source specified.
        if classifier.composites.count():
            X, Y, PID, SID = populate_training_matrix_time(classifier)
        else:
            if classifier.sentineltile:
                rasterlayer_lookup = classifier.sentineltile.rasterlayer_lookup
            else:
                rasterlayer_lookup = None

            try:
                X, Y, PID, SID = populate_training_matrix(
                    classifier.traininglayer,
                    classifier.band_names.split(','),
                    rasterlayer_lookup,
                    classifier.is_regressor,
                    classifier.training_all_touched,
                )
            except ValueError:
                classifier.write(VALUE_CONFIG_ERROR_MSG, classifier.FAILED)
                raise

        # Abort if there are no training pixels with the given configuration.
        if len(Y) == 0:
            classifier.write('No training sample pixels found - can not fit algorithm', classifier.FAILED)
            return

        # Store collected pixels.
        with TemporaryFile() as fl:
            numpy.savez_compressed(fl, X=X, Y=Y, PID=PID, SID=SID)
            name = 'classifier-collected-pixels-{}.npz'.format(classifier.id)
            classifier.collected_pixels.save(name, File(fl))

    # Check consistency of Y values.
    if classifier.is_keras:
        uniques = numpy.unique(Y)
        if not numpy.array_equal(uniques, numpy.arange(numpy.max(Y)) + 1):
            msg = 'Bad Y value configuration. For Keras, class DN require to be a straight sequence from 1 to N wher N is number of classes, found {}.'.format(uniques)
            classifier.write(msg, classifier.FAILED)
            return

    # Log classification setup.
    classifier.write('Found {} training sample pixels - fitting algorithm with tensor X of shape {}.'.format(len(Y), X.shape))
    classifier.write('List of physical devices available: {}'.format(list_physical_devices()))

    # Set fixed random seed if required.
    if classifier.split_random_seed is not None:
        numpy.random.seed(classifier.split_random_seed)

    # Constructing split data based on sample.
    if classifier.split_by_polygon:
        unique_ids = numpy.unique(SID)
        selected_ids = numpy.random.choice(
            unique_ids,
            int(len(unique_ids) * (1 - classifier.splitfraction)),
            replace=False,
        )
        selector = numpy.in1d(SID, selected_ids)
    else:
        selector = numpy.random.random(len(Y)) >= classifier.splitfraction

    clf_args = classifier.clf_args_dict
    fit_args = {}

    # Get the classifier class.
    if classifier.is_keras:
        if not clf_args:
            clf_args = {
                'optimizer': 'adagrad',
                'loss': 'categorical_crossentropy',
                'metrics': ['accuracy'],
            }

        # Instantiate keras classifier and cross check with training data specs.
        try:
            clf = model_from_json(classifier.keras_model_json)
        except:
            classifier.write(KERAS_JSON_MALFORMED_ERROR_MSG, Classifier.FAILED)
            return
        if not len(clf.layers):
            classifier.write(KERAS_MIN_ONE_LAYER_ERROR_MSG, Classifier.FAILED)
            return
        elif not isinstance(clf.layers[-1], Dense):
            classifier.write(KERAS_LAST_LAYER_NOT_DENSE_ERROR_MSG, Classifier.FAILED)
            return
        elif not classifier.is_regressor and clf.layers[-1].units != len(numpy.unique(Y)):
            classifier.write(KERAS_LAST_LAYER_UNITS_ERROR_MSG_TMPL.format(clf.layers[-1].units, len(numpy.unique(Y))), Classifier.FAILED)
            return
        # Instantiate sklean wrapper for keras classifier.
        if classifier.wrap_keras_with_sklearn:
            clf = KerasClassifier(get_keras_model, keras_model_json=classifier.keras_model_json, **clf_args)
        else:
            # Compile model.
            compile_args = {key: val for key, val in clf_args.items() if key not in KERAS_FIT_ARGS}
            clf.compile(**compile_args)
            # Construct fit args.
            fit_args = {key: val for key, val in clf_args.items() if key in KERAS_FIT_ARGS}
            # Make output mode one line per epoch during training.
            if 'verbose' not in fit_args:
                fit_args['verbose'] = 2
            if 'epochs' not in fit_args:
                fit_args['epochs'] = 1
            # Set log callback.
            fit_args['callbacks'] = [LogCallback(classifier, fit_args['epochs'])]
            # Compute class weights if required.
            if classifier.auto_class_weights:
                unique_values, uniue_counts = numpy.unique(Y, return_counts=True)
                class_weight = {int(uniq - 1): float(count / len(Y)) for uniq, count in zip(unique_values, uniue_counts)}
                fit_args['class_weight'] = class_weight
                classifier.write('Class weight: {}'.format(class_weight))
    else:
        # Instantiate sklearn classifier.
        clf_module, clf_class_name = classifier.ALGORITHM_MODULES[classifier.algorithm]
        clf_module = importlib.import_module('sklearn.' + clf_module)
        clf_class = getattr(clf_module, clf_class_name)
        clf = clf_class(**clf_args)

    # Select scaler.
    if len(X.shape) <= 2:
        scaler = RobustScaler()
    else:
        scaler = RNNRobustScaler()

    # Create a pipeline with scaling and classification.
    if not classifier.is_keras or classifier.wrap_keras_with_sklearn:
        clf = Pipeline([
            (PIPELINE_SCALER_NAME, scaler),
            (PIPELINE_ESTIMATOR_NAME, clf),
        ])

    # TF keras cant handle unit16.
    if classifier.is_keras:
        X = X.astype(KERAS_TRAIN_TYPE)

    # Compute train and test arrays. If all available pixels were used for
    #  training, compute accuracy with full dataset.
    if classifier.splitfraction == 0:
        x_train = x_test = X
        y_train = y_test = Y
    else:
        x_train = X[selector]
        y_train = Y[selector]
        x_test = X[numpy.logical_not(selector)]
        y_test = Y[numpy.logical_not(selector)]
        # Remove originals to save memory.
        del X, Y

    # Keras classifiers want y to be a one-hot-encoding matrix. Each class is
    # named after its column index in the matrix. This assumes class category
    # values are sequential and start with 1.
    training_generator = None
    testing_generator = None
    if not classifier.is_regressor and classifier.is_keras and not classifier.wrap_keras_with_sklearn:
        y_train = to_categorical(y_train - 1)
        training_generator = PixelSequence(x_train, y_train, fit_args.pop('batch_size', 100))
        testing_generator = PixelSequence(x_test, batch_size=fit_args.pop('batch_size', 100))

    # Fit the model.
    try:
        if training_generator is None:
            clf.fit(x_train, y_train, **fit_args)
        else:
            clf.fit(training_generator, **fit_args)
    except Exception as exc:
        sentry_sdk.capture_exception(exc)
        classifier.write(FITTING_ERROR_MSG + ': ' + str(exc), classifier.FAILED)
        raise

    # Do Keras related logging.
    if classifier.is_keras:
        if classifier.wrap_keras_with_sklearn:
            keras_model = clf.named_steps[PIPELINE_ESTIMATOR_NAME].model
        else:
            keras_model = clf
        # Write Keras parameters to classifier log.
        classifier.write('Keras parameters: {}'.format(keras_model.history.params))
        # Write Keras model summary to classifier log.
        with io.StringIO() as fl:
            keras_model.summary(print_fn=lambda x: fl.write(x + '\n'))
            classifier.write('Keras summary:\n{}'.format(fl.getvalue()))

    # Instanciate data container model.
    acc, created = ClassifierAccuracy.objects.get_or_create(classifier=classifier)

    # Predict on test pixels.
    if testing_generator is None:
        y_predicted = clf.predict(x_test)
    else:
        y_predicted = clf.predict(testing_generator)

    # Convert keras probability matrix to predicted class array.
    if len(y_predicted.shape) > 1:
        y_predicted = numpy.argmax(y_predicted, axis=1) + 1

    # Compute statistics.
    if classifier.is_regressor:
        # Compute rsquared.
        acc.rsquared = r2_score(y_test, y_predicted)
    else:
        # Compute accuracy matrix and coefficients.
        acc.accuracy_matrix = confusion_matrix(y_test, y_predicted).tolist()
        acc.cohen_kappa = cohen_kappa_score(y_test, y_predicted)
        acc.accuracy_score = accuracy_score(y_test, y_predicted)
    acc.save()

    # Store result in classifier.
    if classifier.is_keras:
        name = 'classifier-{}.hdf5'.format(classifier.id)
        trained_io = io.BytesIO()
        trained = h5py.File(trained_io, 'w')
        if classifier.wrap_keras_with_sklearn:
            keras_model = clf.named_steps[PIPELINE_ESTIMATOR_NAME].model
        else:
            keras_model = clf
        # Save the Keras model.
        keras_model.save(trained)
        trained.flush()
        if classifier.wrap_keras_with_sklearn:
            # Unset the estimator to pickle the pipline.
            clf.named_steps[PIPELINE_ESTIMATOR_NAME].model = None
            # Pickle the pipeline.
            pipe = io.BytesIO(pickle.dumps(clf))

        save_trained = io.BytesIO()
        with zipfile.ZipFile(save_trained, 'w', zipfile.ZIP_DEFLATED) as zf:
            if classifier.wrap_keras_with_sklearn:
                zf.writestr(ZIP_PIPELINE_NAME, pipe.getvalue())
            zf.writestr(ZIP_ESTIMATOR_NAME, trained_io.getvalue())
    else:
        name = 'classifier-{}.pickle'.format(classifier.id)
        save_trained = io.BytesIO(pickle.dumps(clf))

    classifier.trained = File(save_trained, name=name)
    classifier.write('Finished training algorithm', classifier.FINISHED)


def get_aggregationlayer_tile_indices(aggregationlayer, zoom):
    # Set agglayer extent if not precomputed.
    if not aggregationlayer.extent:
        extent = aggregationlayer.aggregationarea_set.aggregate(Extent('geom'))['geom__extent']
        aggregationlayer.extent = Polygon.from_bbox(extent)
        aggregationlayer.save()
    # Create set to hold tile indexes.
    indexranges = set()
    # Loop through all aggregationareas.
    for aggarea in aggregationlayer.aggregationarea_set.all():
        # Get index range from aggregationarea.
        geom = aggarea.geom.transform(WEB_MERCATOR_SRID, clone=True)
        indexrange = tile_index_range(geom.extent, zoom, tolerance=1e-3)
        # Add additional tiles to set.
        for tilex in range(indexrange[0], indexrange[2] + 1):
            for tiley in range(indexrange[1], indexrange[3] + 1):
                indexranges.add((tilex, tiley, zoom))

    for idxr in indexranges:
        yield idxr


def get_prediction_index_range(pred, zoom=ZOOM):
    # Get tile range for aggregationlayer, compositeband or sentineltile for
    # this prediction.
    if not pred.aggregationlayer:
        pred.write('ERROR: {}'.format(PREDICTION_CONFIG_ERROR_MSG), PredictedLayer.FAILED)
        raise ValueError(PREDICTION_CONFIG_ERROR_MSG)
    return get_aggregationlayer_tile_indices(pred.aggregationlayer, zoom)


def predict_sentinel_layer(predicted_layer_id):
    """
    Use a classifier to predict data onto a rasterlayer. The PredictedLayer
    model is the mediator.
    """
    pred = PredictedLayer.objects.get(id=predicted_layer_id)
    pred.predictedlayerchunk_set.all().delete()
    if pred.sieve_threshold > 0:
        if pred.sieve_parent.classifier.is_regressor:
            pred.write(SIEVE_CONIFG_ERROR_MSG, pred.FAILED)
            return
        pred.write('Started sieving layer.', pred.PROCESSING)
    else:
        # Check consistency of composite input with required lenght from classifier.
        composite_count = pred.composites.count()
        if composite_count > 1 and pred.classifier.look_back_steps > 0 and composite_count != pred.classifier.look_back_steps:
            msg = 'Layer configuration error. Number of input composites is not consistent with classifier. Found {} composites, expected {}.'
            pred.write(
                msg.format(composite_count, pred.classifier.look_back_steps),
                pred.FAILED,
            )
            return
        pred.write('Started predicting layer.', pred.PROCESSING)

    # Get tile range for compositeband or sentineltile for this prediction.
    tiles = get_prediction_index_range(pred)

    # Push tasks for sentinel chunks.
    counter = 0
    for tile_index in tiles:
        counter += 1
        if counter % pred.chunk_size == 0:
            chunk = PredictedLayerChunk.objects.create(
                predictedlayer=pred,
                from_index=counter - pred.chunk_size,
                to_index=counter,
                status=PredictedLayerChunk.PENDING,
            )
            if pred.sieve_threshold > 0:
                ecs.sieve_sentinel_chunk(chunk.id)
            else:
                ecs.predict_sentinel_chunk(chunk.id)

    # Push the remaining index range as well.
    rest = counter % pred.chunk_size
    if rest:
        chunk = PredictedLayerChunk.objects.create(
            predictedlayer=pred,
            from_index=counter - rest,
            to_index=counter,
            status=PredictedLayerChunk.PENDING,
        )
        if pred.sieve_threshold > 0:
            ecs.sieve_sentinel_chunk(chunk.id)
        else:
            ecs.predict_sentinel_chunk(chunk.id)

    # Log how many chunks need to be processed.
    pred.refresh_from_db()
    pred.write('Task will require {} chunks.'.format(pred.predictedlayerchunk_set.count()))


def predict_sentinel_chunk(chunk_id):
    """
    Predict over a group of tiles.
    """
    # Get chunk.
    chunk = PredictedLayerChunk.objects.get(id=chunk_id)
    # Update chunk status.
    chunk.status = PredictedLayerChunk.PROCESSING
    chunk.save()
    # Get global tile range.
    tiles = get_prediction_index_range(chunk.predictedlayer)
    # Get band names for data matrix construction.
    band_names = chunk.predictedlayer.classifier.band_names.split(',')
    # Get rasterlayer ids.
    composite_count = chunk.predictedlayer.composites.count()
    if chunk.predictedlayer.sentineltile:
        is_rnn = False
        rasterlayer_lookup = chunk.predictedlayer.sentineltile.rasterlayer_lookup
    elif composite_count == 0:
        is_rnn = True
        rasterlayer_lookup = [composite.rasterlayer_lookup for composite in chunk.predictedlayer.classifier.composites.all()]
    elif composite_count == 1:
        is_rnn = False
        rasterlayer_lookup = chunk.predictedlayer.composites.first().rasterlayer_lookup
    elif composite_count > 1:
        # We have previously ensured that this predicted layer has the right
        # number of composites to do the "look-back"
        is_rnn = True
        rasterlayer_lookup = [composite.rasterlayer_lookup for composite in chunk.predictedlayer.composites.all()]
    # Predict tiles over this chunk's range.
    for tilex, tiley, tilez in list(tiles)[chunk.from_index:chunk.to_index]:
        if is_rnn:
            data = []
            for lookup in rasterlayer_lookup:
                # Convert lookup to id list.
                rasterlayer_ids = get_rasterlayer_ids(band_names, lookup)
                # Get data from tiles for prediction.
                pixels = get_classifier_data(rasterlayer_ids, tilez, tilex, tiley)
                data.append(pixels)
                if pixels is None:
                    data = None
                    break
            if data is None:
                continue
            # Reshape array to right format.
            data = numpy.swapaxes(numpy.array(data), 0, 1)
        else:
            # Convert lookup to id list.
            rasterlayer_ids = get_rasterlayer_ids(band_names, rasterlayer_lookup)
            # Get data from tiles for prediction.
            data = get_classifier_data(rasterlayer_ids, tilez, tilex, tiley)
            if data is None:
                continue
        # Determine numpy and GDAL datatypes.
        dtype = REGRESSION_DATATYPE if chunk.predictedlayer.classifier.is_regressor else CLASSIFICATION_DATATYPE
        dtype_gdal = REGRESSION_DATATYPE_GDAL if chunk.predictedlayer.classifier.is_regressor else CLASSIFICATION_DATATYPE_GDAL
        # TF keras cant handle unit16.
        if chunk.predictedlayer.classifier.is_keras:
            data = data.astype(KERAS_TRAIN_TYPE)
        # Predict classes.
        predicted = chunk.predictedlayer.classifier.clf.predict(data)
        # If the model is a Keras model and not a Sklearn Pipeline, the prediction
        # is a probability matrix and needs to be converted to a predicted array.
        # This also assumes 1-N indexing of classes in digital numbers (DN),
        # i.e. classi DN are sequential and start with 1.
        nr_of_bands = 1
        nodata_value = SENTINEL_NODATA_VALUE
        if not isinstance(chunk.predictedlayer.classifier.clf, Pipeline) and not chunk.predictedlayer.classifier.is_regressor:
            if chunk.predictedlayer.store_class_probabilities:
                # Store the predicted probabilities separate bands.
                predicted = [numpy.ascontiguousarray(255 * probability, dtype=dtype) for probability in predicted.swapaxes(0, 1)]
                # Specify the number of bands to write as number of classes.
                nr_of_bands = len(predicted)
                nodata_value = None
            else:
                # Convert predicted into category index numbers.
                predicted = numpy.argmax(predicted, axis=1) + 1
                # Enforce correct dtype.
                predicted = predicted.astype(dtype)
        # Write predicted pixels into a tile.
        write_raster_tile(
            chunk.predictedlayer.rasterlayer_id,
            predicted,
            tilez,
            tilex,
            tiley,
            nodata_value=nodata_value,
            datatype=dtype_gdal,
            merge_with_existing=False,
            nr_of_bands=nr_of_bands,
        )

    # Log progress, update chunks done count.
    chunk.status = PredictedLayerChunk.FINISHED
    chunk.save()

    # If all chunks have completed, push pyramid build job.
    if PredictedLayerChunk.objects.filter(predictedlayer=chunk.predictedlayer).exclude(status=PredictedLayerChunk.FINISHED).count() == 0:
        chunk.predictedlayer.write('Finished layer prediction at full resolution')
        ecs.build_predicted_pyramid(chunk.predictedlayer.id)


def sieve_sentinel_chunk(chunk_id):
    """
    Sieve a group of tiles.
    """
    # Get chunk.
    chunk = PredictedLayerChunk.objects.get(id=chunk_id)
    # Update chunk status.
    chunk.status = PredictedLayerChunk.PROCESSING
    chunk.save()
    # Get global tile range.
    tiles = list(get_prediction_index_range(chunk.predictedlayer))
    # Prefetch all parent tiles for this chunk.
    all_tiles = {}
    for tilex, tiley, tilez in tiles[chunk.from_index:chunk.to_index]:
        tile = get_raster_tile(chunk.predictedlayer.sieve_parent.rasterlayer_id, tilez=tilez, tilex=tilex, tiley=tiley, look_up=False)
        if tile:
            all_tiles[(tilex, tiley)] = tile.bands[0].data()
    # Create blank array.
    blank = numpy.zeros((WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE), CLASSIFICATION_DATATYPE)
    # Sieve by constructing tile plus surrounding tiles.
    for tilex, tiley, tilez in tiles[chunk.from_index:chunk.to_index]:
        # Construct pixel area around center tile.
        data = []
        for i in [-1, 0, 1]:
            column = []
            for j in [-1, 0, 1]:
                tile = all_tiles.get((tilex + i, tiley + j), blank)
                column.append(tile)
            data.append(numpy.vstack(column))
        data = numpy.hstack(data)
        # Construct mask for sieving.
        mask = data != CLASSIFICATION_NODATA
        # Sieve raster.
        sieved = sieve(data, chunk.predictedlayer.sieve_threshold, mask=mask, connectivity=chunk.predictedlayer.sieve_connectivity)
        # Extract center pixels.
        result = sieved[WEB_MERCATOR_TILESIZE:(2 * WEB_MERCATOR_TILESIZE), WEB_MERCATOR_TILESIZE:(2 * WEB_MERCATOR_TILESIZE)]
        # Convert to classification datatype.
        result = result.astype(CLASSIFICATION_DATATYPE)
        # Write tile.
        write_raster_tile(
            layer_id=chunk.predictedlayer.rasterlayer_id,
            result=result,
            tilez=tilez,
            tilex=tilex,
            tiley=tiley,
            nodata_value=CLASSIFICATION_NODATA,
            datatype=CLASSIFICATION_DATATYPE_GDAL,
            merge_with_existing=False,
        )

    # Log progress.
    chunk.status = PredictedLayerChunk.FINISHED
    chunk.save()

    # If all chunks have completed, push pyramid build job.
    if PredictedLayerChunk.objects.filter(predictedlayer=chunk.predictedlayer).exclude(status=PredictedLayerChunk.FINISHED).count() == 0:
        chunk.predictedlayer.write('Finished layer sieving at full resolution')
        ecs.build_predicted_pyramid(chunk.predictedlayer.id)


def build_predicted_pyramid(predicted_layer_id):
    """
    Build an overview stack over a predicted layer.
    """
    pred = PredictedLayer.objects.get(id=predicted_layer_id)

    pred.write('Started building pyramid')

    # Determine numpy and GDAL datatypes.
    is_regressor = pred.classifier.is_regressor if pred.classifier else pred.sieve_parent.classifier.is_regressor
    dtype = REGRESSION_DATATYPE if is_regressor else CLASSIFICATION_DATATYPE
    dtype_gdal = REGRESSION_DATATYPE_GDAL if is_regressor else CLASSIFICATION_DATATYPE_GDAL

    # Loop through the tiles in each zoom level, bottom up.
    for tilez in range(ZOOM - 1, -1, -1):
        pred.write('Building pyramid at zoom level {}'.format(tilez))

        for tilex, tiley, tilez in get_prediction_index_range(pred, tilez):
            # Get tile data.
            tiles = [
                get_raster_tile(pred.rasterlayer_id, tilez=tilez + 1, tilex=tilex * 2, tiley=tiley * 2, look_up=False),
                get_raster_tile(pred.rasterlayer_id, tilez=tilez + 1, tilex=tilex * 2 + 1, tiley=tiley * 2, look_up=False),
                get_raster_tile(pred.rasterlayer_id, tilez=tilez + 1, tilex=tilex * 2, tiley=tiley * 2 + 1, look_up=False),
                get_raster_tile(pred.rasterlayer_id, tilez=tilez + 1, tilex=tilex * 2 + 1, tiley=tiley * 2 + 1, look_up=False),
            ]
            # Continue if no tiles were found.
            if not len([tile for tile in tiles if tile is not None]):
                continue
            # Extract pixel values.
            tile_data = [
                numpy.zeros((WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE)).astype(dtype) if tile is None else tile.bands[0].data() for tile in tiles
            ]
            # Aggregate tile to lower resolution.
            tile_data = [aggregate_tile(tile, target_dtype=tile.dtype, discrete=tile.dtype is CLASSIFICATION_DATATYPE) for tile in tile_data]
            # Combine data to larger tile.
            tile_data = numpy.concatenate([
                numpy.concatenate(tile_data[:2], axis=1),
                numpy.concatenate(tile_data[2:], axis=1),
            ])
            # Write tile.
            write_raster_tile(
                layer_id=pred.rasterlayer_id,
                result=tile_data,
                tilez=tilez,
                tilex=tilex,
                tiley=tiley,
                nodata_value=CLASSIFICATION_NODATA,
                datatype=dtype_gdal,
            )

    pred.write('Finished building pyramid, prediction task completed.', pred.FINISHED)

    # Push report job.
    push_reports('predictedlayer', pred.id)
