import importlib
import io
import os
import pickle
import zipfile

import h5py
import numpy
from keras.models import model_from_json
from keras.wrappers.scikit_learn import KerasClassifier
from raster.models import RasterTile
from raster.rasterize import rasterize
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import tile_bounds, tile_index_range
from sklearn.metrics import accuracy_score, cohen_kappa_score, confusion_matrix
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import RobustScaler

from classify.const import (
    CHUNK_SIZE, CLASSIFICATION_DATATYPE, CLASSIFICATION_DATATYPE_GDAL, PIPELINE_ESTIMATOR_NAME, PIPELINE_SCALER_NAME,
    PREDICTION_CONFIG_ERROR_MSG, REGRESSION_DATATYPE, REGRESSION_DATATYPE_GDAL, SCALE, SENTINEL_PIXELTYPE,
    VALUE_CONFIG_ERROR_MSG, ZIP_ESTIMATOR_NAME, ZIP_PIPELINE_NAME, ZOOM
)
from classify.models import Classifier, ClassifierAccuracy, PredictedLayer, PredictedLayerChunk, TrainingLayerExport
from classify.utils import RNNRobustScaler
from django.contrib.gis.db.models import Extent
from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos import Polygon
from django.core.files import File
from sentinel import ecs
from sentinel.utils import aggregate_tile, get_raster_tile, write_raster_tile


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
        else:
            raise ValueError('Band names have to be similar to either B01 or RL23.')

    return rasterlayer_ids


def populate_training_matrix(traininglayer, band_names, rasterlayer_lookup=None, is_regressor=False):
    # Determine sample value datatype.
    target_type = REGRESSION_DATATYPE if is_regressor else CLASSIFICATION_DATATYPE
    # Create numpy arrays holding training data.
    number_of_bands = len(band_names)
    X = numpy.empty(shape=(0, number_of_bands), dtype=SENTINEL_PIXELTYPE)
    Y = numpy.empty(shape=(0, ), dtype=target_type)
    # Track pixel IDs to allow merging different training matrices from
    # different traininglayers.
    PID = numpy.empty(shape=(0, ), dtype='int64')
    # Dictionary for categories or statistics.
    categories = {}
    # Loop through training tiles to build training set.
    for sample in traininglayer.trainingsample_set.all():
        # Check for consistency in training samples for dicrete datasets.
        if not is_regressor:
            if sample.category in categories:
                if sample.value != categories[sample.category]:
                    raise ValueError(VALUE_CONFIG_ERROR_MSG)
            else:
                categories[sample.category] = sample.value if is_regressor else int(sample.value)
        # Take rasterlayer lookup from the trainingsample if it was not
        # provided as input.
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
                sample_rast = rasterize(sample.geom, rast, all_touched=True)
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

    return X, Y, PID


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
    for composite in classifier.composites.all():
        classifier.write('Collecting training data for "{}"'.format(composite))
        rasterlayer_lookup = composite.rasterlayer_lookup
        try:
            X, Y, PID = populate_training_matrix(
                classifier.traininglayer,
                classifier.band_names.split(','),
                rasterlayer_lookup,
                classifier.is_regressor,
            )
        except ValueError:
            classifier.write(VALUE_CONFIG_ERROR_MSG, classifier.FAILED)
            raise

        if Xs is None:
            Xs = X
            Ys = Y
            PIDs = PID
        else:
            Ys = numpy.hstack([Ys, Y])
            Xs = numpy.vstack([Xs, X])
            PIDs = numpy.hstack([PIDs, PID])
    # Combine data
    all_data = numpy.vstack([PIDs, Ys, Xs.T]).T
    # Sort by PID
    all_data = all_data[PIDs.argsort()]
    # Split into groups.
    all_data = numpy.array(numpy.vsplit(all_data, numpy.unique(PIDs).shape[0]))
    # Extract individual arrays.
    PIDs = all_data[:, 0, 0]
    Ys = all_data[:, 0, 1]
    Xs = all_data[:, :, 2:]
    return Xs, Ys, PIDs


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
    else:
        classifier.write('Started collecting training data', classifier.PROCESSING)

    # Remove current accuracy matrix.
    if hasattr(classifier, 'classifieraccuracy'):
        classifier.classifieraccuracy.delete()

    # Check if pixels have already been collected.
    if classifier.collected_pixels.name:
        action = 'Loaded from file'
        loaded = numpy.load(classifier.collected_pixels)
        X = loaded['X']
        Y = loaded['Y']
        PID = loaded['PID']
    else:
        action = 'Collected'
        # Check if the classifier has a custom data source specified.
        if classifier.composites.count():
            X, Y, PID = populate_training_matrix_time(classifier)
        else:
            if classifier.sentineltile:
                rasterlayer_lookup = classifier.sentineltile.rasterlayer_lookup
            else:
                rasterlayer_lookup = None

            try:
                X, Y, PID = populate_training_matrix(
                    classifier.traininglayer,
                    classifier.band_names.split(','),
                    rasterlayer_lookup,
                    classifier.is_regressor,
                )
            except ValueError:
                classifier.write(VALUE_CONFIG_ERROR_MSG, classifier.FAILED)
                raise

        # Abort if there are no training pixels with the given configuration.
        if len(Y) == 0:
            classifier.write('No training sample pixels found - can not fit algorithm', classifier.FAILED)
            return

        # Store collected pixels.
        with io.BytesIO() as fl:
            numpy.savez_compressed(fl, X=X, Y=Y, PID=PID)
            name = 'classifier-collected-pixels-{}.pickle'.format(classifier.id)
            classifier.collected_pixels.save(name, File(fl))

    classifier.write('{} {} training sample pixels - fitting algorithm with tensor X of shape {}.'.format(action, len(Y), X.shape))

    # Constructing split data.
    selector = numpy.random.random(len(Y)) >= classifier.splitfraction

    clf_args = classifier.clf_args_dict

    # Get the classifier class.
    if classifier.is_keras:
        if not clf_args:
            clf_args = {
                'optimizer': 'adagrad',
                'loss': 'categorical_crossentropy',
                'metrics': ['accuracy'],
            }
        clf = KerasClassifier(get_keras_model, keras_model_json=classifier.keras_model_json, **clf_args)
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
    clf = Pipeline([
        (PIPELINE_SCALER_NAME, scaler),
        (PIPELINE_ESTIMATOR_NAME, clf),
    ])

    # Fit the model.
    clf.fit(X[selector], Y[selector])

    # Do Keras related logging.
    if classifier.is_keras:
        # Get training accuracy history per epoch.
        hist_str = ''
        hist = clf.named_steps[PIPELINE_ESTIMATOR_NAME].model.history.history
        epochs = len(hist['loss'])
        # Write Keras parameters to classifier log.
        classifier.write('Keras parameters: {}'.format(clf.named_steps[PIPELINE_ESTIMATOR_NAME].model.history.params))
        # Write Keras model summary to classifier log.
        with io.StringIO() as fl:
            clf.named_steps[PIPELINE_ESTIMATOR_NAME].model.summary(print_fn=lambda x: fl.write(x + '\n'))
            classifier.write('Keras summary:\n{}'.format(fl.getvalue()))
        # Write Keras training history to classifier log.
        for i in range(epochs):
            hist_str += 'Epoch {}/{} - loss {:.4f} - acc {:.4f}\n'.format(i + 1, epochs, hist['loss'][i], hist['acc'][i])
        classifier.write('Keras history:\n{}'.format(hist_str))

    # Compute validation arrays. If full arrays were used for training, the
    # validation array is empty. In this case, compute accuracy agains full
    # dataset.
    if numpy.all(selector):
        validation_pixels = X
        control_pixels = Y
    else:
        validation_pixels = X[numpy.logical_not(selector)]
        control_pixels = Y[numpy.logical_not(selector)]

    # Instanciate data container model.
    acc, created = ClassifierAccuracy.objects.get_or_create(classifier=classifier)

    if classifier.is_regressor:
        # Compute rsquared.
        acc.rsquared = clf.score(validation_pixels, control_pixels)
    else:
        # Predict validation pixels.
        validation_pixels = clf.predict(validation_pixels)
        # Compute accuracy matrix and coefficients.
        acc.accuracy_matrix = confusion_matrix(control_pixels, validation_pixels).tolist()
        acc.cohen_kappa = cohen_kappa_score(control_pixels, validation_pixels)
        acc.accuracy_score = accuracy_score(control_pixels, validation_pixels)
    acc.save()

    # Store result in classifier.
    if classifier.is_keras:
        name = 'classifier-{}.hdf5'.format(classifier.id)
        trained_io = io.BytesIO()
        trained = h5py.File(trained_io)
        # Save the Keras model.
        clf.named_steps[PIPELINE_ESTIMATOR_NAME].model.save(trained)
        trained.flush()
        # Unset the estimator to pickle the pipline.
        clf.named_steps[PIPELINE_ESTIMATOR_NAME].model = None
        # Pickle the pipeline.
        pipe = io.BytesIO(pickle.dumps(clf))

        save_trained = io.BytesIO()

        with zipfile.ZipFile(save_trained, 'w', zipfile.ZIP_DEFLATED) as zf:
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
    # Compute indexrange.
    index_range = tile_index_range(aggregationlayer.extent.extent, zoom)
    for idx in range(index_range[0], index_range[2] + 1):
        for idy in range(index_range[1], index_range[3] + 1):
            yield (idx, idy, zoom)


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
    pred.write('Started predicting layer.', pred.PROCESSING)

    # Get tile range for compositeband or sentineltile for this prediction.
    tiles = get_prediction_index_range(pred)

    # Push tasks for sentinel chunks.
    counter = 0
    for tile_index in tiles:
        counter += 1
        if counter % CHUNK_SIZE == 0:
            chunk = PredictedLayerChunk.objects.create(
                predictedlayer=pred,
                from_index=counter - CHUNK_SIZE,
                to_index=counter,
                status=PredictedLayerChunk.PENDING,
            )
            ecs.predict_sentinel_chunk(chunk.id)

    # Push the remaining index range as well.
    rest = counter % CHUNK_SIZE
    if rest:
        chunk = PredictedLayerChunk.objects.create(
            predictedlayer=pred,
            from_index=counter - rest,
            to_index=counter,
            status=PredictedLayerChunk.PENDING,
        )
        ecs.predict_sentinel_chunk(chunk.id)

    # Log how many chunks need to be processed.
    pred.refresh_from_db()
    pred.write('Prediction will require {} chunks.'.format(pred.predictedlayerchunk_set.count()))


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
    is_rnn = False
    if chunk.predictedlayer.classifier.composites.count() > 1:
        is_rnn = True
        rasterlayer_lookup = [composite.rasterlayer_lookup for composite in chunk.predictedlayer.classifier.composites.all()]
    elif chunk.predictedlayer.composite_id:
        rasterlayer_lookup = chunk.predictedlayer.composite.rasterlayer_lookup
    else:
        rasterlayer_lookup = chunk.predictedlayer.sentineltile.rasterlayer_lookup
    # Predict tiles over this chunk's range.
    batch = []
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
        # Predict classes.
        predicted = chunk.predictedlayer.classifier.clf.predict(data).astype(dtype)
        # Write predicted pixels into a tile.
        tile_to_register = write_raster_tile(chunk.predictedlayer.rasterlayer_id, predicted, tilez, tilex, tiley, datatype=dtype_gdal)
        # Append tile to batch.
        if tile_to_register:
            batch.append(tile_to_register)
        # Commit batch if size is reached.
        if len(batch) >= CHUNK_SIZE:
            RasterTile.objects.bulk_create(batch)
            batch = []

    # Commit remaining tiles if present.
    if len(batch) > 0:
        RasterTile.objects.bulk_create(batch)

    # Log progress, update chunks done count.
    chunk.status = PredictedLayerChunk.FINISHED
    chunk.save()

    # If all chunks have completed, push pyramid build job.
    if PredictedLayerChunk.objects.filter(predictedlayer=chunk.predictedlayer).exclude(status=PredictedLayerChunk.FINISHED).count() == 0:
        chunk.predictedlayer.write('Finished layer prediction at full resolution')
        ecs.build_predicted_pyramid(chunk.predictedlayer.id)


def build_predicted_pyramid(predicted_layer_id):
    """
    Build an overview stack over a predicted layer.
    """
    pred = PredictedLayer.objects.get(id=predicted_layer_id)

    pred.write('Started building pyramid')

    # Loop through the tiles in each zoom level, bottom up.
    batch = []
    for tilez in range(ZOOM - 1, -1, -1):
        pred.write('Building pyramid at zoom level {}'.format(tilez))

        for tilex, tiley, tilez in get_prediction_index_range(pred, tilez):
            # Get tile data.
            tiles = [
                get_raster_tile(pred.rasterlayer_id, tilez=tilez + 1, tilex=tilex * 2, tiley=tiley * 2),
                get_raster_tile(pred.rasterlayer_id, tilez=tilez + 1, tilex=tilex * 2 + 1, tiley=tiley * 2),
                get_raster_tile(pred.rasterlayer_id, tilez=tilez + 1, tilex=tilex * 2, tiley=tiley * 2 + 1),
                get_raster_tile(pred.rasterlayer_id, tilez=tilez + 1, tilex=tilex * 2 + 1, tiley=tiley * 2 + 1),
            ]
            # Continue if no tiles were found.
            if not len([tile for tile in tiles if tile is not None]):
                continue
            # Extract pixel values.
            tile_data = [
                numpy.zeros((WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE)) if tile is None else tile.bands[0].data() for tile in tiles
            ]
            # Aggregate tile to lower resolution.
            tile_data = [aggregate_tile(tile, target_dtype=tile.dtype, discrete=tile.dtype is CLASSIFICATION_DATATYPE) for tile in tile_data]
            # Combine data to larger tile.
            tile_data = numpy.concatenate([
                numpy.concatenate(tile_data[:2], axis=1),
                numpy.concatenate(tile_data[2:], axis=1),
            ])
            # Write tile.
            tile_to_register = write_raster_tile(
                layer_id=pred.rasterlayer_id,
                result=tile_data,
                tilez=tilez,
                tilex=tilex,
                tiley=tiley,
                nodata_value=0,
                datatype=1,
            )
            # Append tile to batch.
            if tile_to_register:
                batch.append(tile_to_register)
            # Commit batch if size is reached.
            if len(batch) >= CHUNK_SIZE:
                RasterTile.objects.bulk_create(batch)
                batch = []

    # Commit remaining tiles if present.
    if len(batch) > 0:
        RasterTile.objects.bulk_create(batch)

    pred.write('Finished building pyramid, prediction task completed.', pred.FINISHED)


def export_training_data(traininglayerexport_id, bands_to_export='B01,B02,B03,B04,B05,B06,B07,B08,B8A,B09,B10,B11,B12'):
    """
    Export training data to a file over a date range for monthly composites.
    """
    # Get export object.
    exp = TrainingLayerExport.objects.get(pk=traininglayerexport_id)
    exp.write('Starting training data export.')

    # Get rasterlayer lookup if source was provided.
    rasterlayer_lookup = None
    if exp.composite:
        rasterlayer_lookup = exp.composite.rasterlayer_lookup
    elif exp.sentineltile:
        rasterlayer_lookup = exp.sentineltile.rasterlayer_lookup

    # Export all bands.
    bands_to_export = bands_to_export.split(',')

    # Get training data for this composite as floating point data.
    exp.write('Extracting pixel values.')
    X, Y, PID = populate_training_matrix(exp.traininglayer, bands_to_export, rasterlayer_lookup, is_regressor=exp.traininglayer.continuous)

    # Write data to compressed numpy file.
    exp.write('Writing pixel values to compressed numpy file (npz).')
    npz_name = 'traininglayer-export-{}.npz'.format(exp.id)
    npz_path = os.path.join('/tmp/', npz_name)
    numpy.savez_compressed(npz_path, X=X, Y=Y, PID=PID)

    # Save table in export instance.
    exp.write('Uploading file to remote storage.')
    exp.data = File(open(npz_path, 'rb'), name=npz_name)
    exp.save()
    exp.write('Finished exporting training data.')
