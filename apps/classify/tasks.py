import importlib
import io
import os
import pickle

import numpy
from raster.models import RasterTile
from raster.rasterize import rasterize
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import tile_bounds, tile_index_range
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler

from classify.const import (
    CHUNK_SIZE, CLASSIFICATION_DATATYPE, CLASSIFICATION_DATATYPE_GDAL, REGRESSION_DATATYPE, REGRESSION_DATATYPE_GDAL,
    SCALE, SENTINEL_PIXELTYPE, VALUE_CONFIG_ERROR_MSG, ZOOM
)
from classify.models import Classifier, ClassifierAccuracy, PredictedLayer, PredictedLayerChunk, TrainingLayerExport
from django.contrib.gis.db.models import Extent
from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos import Polygon
from django.core.files import File
from sentinel import ecs
from sentinel.utils import (
    aggregate_tile, get_composite_tile_indices, get_raster_tile, get_sentinel_tile_indices, write_raster_tile
)


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
        # Loop over index range for tiles intersecting with the sample geom.
        idx = tile_index_range(sample.geom.transform(3857, clone=True).extent, ZOOM)
        for tilex in range(idx[0], idx[2] + 1):
            for tiley in range(idx[1], idx[3] + 1):
                # Take rasterlayer lookup from the trainingsample if not
                # it was not provided as input.
                if not rasterlayer_lookup:
                    if sample.composite:
                        rasterlayer_lookup = sample.composite.rasterlayer_lookup
                    else:
                        rasterlayer_lookup = sample.sentineltile.rasterlayer_lookup
                # Convert lookup to id list.
                rasterlayer_ids = get_rasterlayer_ids(band_names, rasterlayer_lookup)
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


def train_sentinel_classifier(classifier_id):
    """
    Trains a classifier based on the registered tiles and sample data.
    """
    # Import sklearn here, its not installed in web app servers.
    from sklearn.metrics import confusion_matrix, cohen_kappa_score, accuracy_score

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

    # Check if the classifier has a custom data source specified.
    if classifier.composite:
        rasterlayer_lookup = classifier.composite.rasterlayer_lookup
    elif classifier.sentineltile:
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

    classifier.write('Collected {} training sample pixels - fitting algorithm'.format(len(Y)))

    # Constructing split data.
    selector = numpy.random.random(len(Y)) >= classifier.splitfraction

    # Get the classifier class.
    clf_module, clf_class_name = classifier.ALGORITHM_MODULES[classifier.algorithm]
    clf_module = importlib.import_module('sklearn.' + clf_module)
    clf_class = getattr(clf_module, clf_class_name)

    # Convert numerical arguments to numbers so that the input types match. This
    # is necessary because the hstore field does not convert types back, it
    # stores everything as strings.
    args = {}
    for key, val in classifier.clf_args.items():
        try:
            val = int(val)
        except ValueError:
            try:
                val = float(val)
            except ValueError:
                pass
        args[key] = val

    # Create a pipeline with scaling and classification.
    clf = make_pipeline(RobustScaler(), clf_class(**args))

    # Fit the pipeline.
    clf.fit(X[selector, :], Y[selector])

    # Compute validation arrays. If full arrays were used for training, the
    # validation array is empty. In this case, compute accuracy agains full
    # dataset.
    if numpy.all(selector):
        validation_pixels = X
        control_pixels = Y
    else:
        validation_pixels = X[numpy.logical_not(selector), :]
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
    name = 'classifier-{}.pickle'.format(classifier.id)
    classifier.trained = File(io.BytesIO(pickle.dumps(clf)), name=name)
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
    if pred.aggregationlayer:
        return get_aggregationlayer_tile_indices(pred.aggregationlayer, zoom)
    elif pred.composite:
        return get_composite_tile_indices(pred.composite, zoom)
    else:
        return get_sentinel_tile_indices(pred.sentineltile, zoom)


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
    if chunk.predictedlayer.composite_id:
        rasterlayer_lookup = chunk.predictedlayer.composite.rasterlayer_lookup
    else:
        rasterlayer_lookup = chunk.predictedlayer.sentineltile.rasterlayer_lookup
    # Predict tiles over this chunk's range.
    batch = []
    for tilex, tiley, tilez in list(tiles)[chunk.from_index:chunk.to_index]:
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

    # Get rasterlayer lookup if source was provided.
    rasterlayer_lookup = None
    if exp.composite:
        rasterlayer_lookup = exp.composite.rasterlayer_lookup
    elif exp.sentineltile:
        rasterlayer_lookup = exp.sentineltile.rasterlayer_lookup

    # Export all bands.
    bands_to_export = bands_to_export.split(',')

    # Get training data for this composite as floating point data.
    X, Y, PID = populate_training_matrix(exp.traininglayer, bands_to_export, rasterlayer_lookup, is_regressor=exp.traininglayer.continuous)

    # Append training class values to pixel matrix.
    data = numpy.append(Y.reshape((len(Y), 1)), X, 1)

    # Append training class names to pixel matrix if this is a discrete dataset.
    if not exp.traininglayer.continuous:
        names = numpy.chararray(Y.shape, itemsize=max(len(category_name) for category_name in exp.traininglayer.legend.values()))
        for category_dn, category_name in exp.traininglayer.legend.items():
            names[Y == int(category_dn)] = category_name
        data = numpy.append(names.reshape((len(names), 1)), data, 1)

    # Append pixel ids to matrix.
    data = numpy.append(PID.reshape((len(PID), 1)).astype('int64'), data, 1)

    # Append header to matrix, the class name column is only present for
    # discrete datasets.
    if exp.traininglayer.continuous:
        header = numpy.array(['PixelId', 'ClassDigitalNumber'] + bands_to_export)
    else:
        header = numpy.array(['PixelId', 'ClassName', 'ClassDigitalNumber'] + bands_to_export)

    data = numpy.append(header.reshape((1, len(header))), data, 0)

    # Write data to compressed numpy file.
    npz_name = 'traininglayer-export-{}.npz'.format(exp.id)
    npz_path = os.path.join('/tmp/', npz_name)
    numpy.savez_compressed(npz_path, X=X, Y=Y, PID=PID)

    # Save table in export instance.
    exp.data = File(open(npz_path, 'rb'), name=npz_name)
    exp.save()
