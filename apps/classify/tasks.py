import importlib
import io
import os
import pickle

import numpy
from raster.rasterize import rasterize
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.lookup import get_raster_tile
from raster.tiles.utils import tile_bounds, tile_index_range, tile_scale

from classify.models import (
    Classifier, ClassifierAccuracy, PredictedLayer, PredictedLayerChunk, TrainingLayer, TrainingLayerExport
)
from django.contrib.gis.db.models import Extent
from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos import Polygon
from django.core.files import File
from sentinel import ecs
from sentinel.models import Composite
from sentinel.utils import aggregate_tile, get_composite_tile_indices, get_sentinel_tile_indices, write_raster_tile

ZOOM = 14

SCALE = tile_scale(ZOOM)

PIXELTYPE = 2

CLASSIFY_BAND_NAMES = (
    'B02.jp2', 'B03.jp2', 'B04.jp2', 'B05.jp2', 'B06.jp2', 'B07.jp2', 'B08.jp2',
    'B8A.jp2', 'B09.jp2', 'B10.jp2', 'B11.jp2', 'B12.jp2',
)

VALUE_CONFIG_ERROR_MSG = 'Found different values for same category.'


def get_classifier_data(rasterlayer_lookup, tilez, tilex, tiley):
    """
    Builds the 13 band training tile file for a training tile instance.
    """
    # Get data for a tile of this scene.
    result = []
    for band in CLASSIFY_BAND_NAMES:
        layer_id = rasterlayer_lookup.get(band)
        tile = get_raster_tile(layer_id, tilez=tilez, tilex=tilex, tiley=tiley)
        if not tile:
            return
        result.append(tile.bands[0].data().ravel())

    return numpy.array(result).T


def populate_training_matrix(traininglayer):
    # Create numpy arrays holding training data.
    NUMBER_OF_BANDS = len(CLASSIFY_BAND_NAMES)
    X = numpy.empty(shape=(0, NUMBER_OF_BANDS), dtype='uint16')
    Y = numpy.empty(shape=(0, ), dtype='uint8')
    PID = numpy.empty(shape=(0, ), dtype='int64')
    # Dictionary for categories.
    categories = {}
    # Loop through training tiles to build training set.
    for sample in traininglayer.trainingsample_set.all():
        # Check for consistency in training samples
        if sample.category in categories:
            if sample.value != categories[sample.category]:
                raise ValueError(VALUE_CONFIG_ERROR_MSG)
        else:
            categories[sample.category] = sample.value
        # Loop over index range for tiles intersecting with the sample geom.
        idx = tile_index_range(sample.geom.transform(3857, clone=True).extent, ZOOM)
        for tilex in range(idx[0], idx[2] + 1):
            for tiley in range(idx[1], idx[3] + 1):
                if sample.composite:
                    rasterlayer_lookup = sample.composite.rasterlayer_lookup
                else:
                    rasterlayer_lookup = sample.sentineltile.rasterlayer_lookup
                # Get stacked tile data for this tile.
                data = get_classifier_data(rasterlayer_lookup, ZOOM, tilex, tiley)
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
                        'datatype': PIXELTYPE,
                        'nr_of_bands': 1,
                    }
                )
                # Rasterize the sample area.
                sample_rast = rasterize(sample.geom, rast, all_touched=True)
                # Create a selector boolean array from rasterized geometry.
                sample_pixels = sample_rast.bands[0].data().ravel()
                selector = sample_pixels == 1
                # Create a constant array with sample value for all intersecting pixels.
                sample_values = sample.value * numpy.ones(sum(selector))
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
    classifier.write('Started collecting training data', classifier.PROCESSING)

    try:
        X, Y, PID = populate_training_matrix(classifier.traininglayer)
    except ValueError:
        classifier.write(VALUE_CONFIG_ERROR_MSG, classifier.FAILED)
        raise

    classifier.write('Collected {} training sample pixels - fitting algorithm'.format(len(Y)))

    # Constructing split data.
    selector = numpy.random.random(len(Y)) >= classifier.splitfraction

    # Instanciate and fit the classifier.
    clf_mod, clf_class = classifier.ALGORITHM_MODULES[classifier.algorithm]
    clf_mod = importlib.import_module('sklearn.' + clf_mod)
    clf = getattr(clf_mod, clf_class)()
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

    # Predict validation pixels.
    validation_pixels = clf.predict(validation_pixels)

    # Instanciate data container model.
    acc, created = ClassifierAccuracy.objects.get_or_create(classifier=classifier)

    # Compute accuracy matrix and coefficients.
    acc.accuracy_matrix = confusion_matrix(control_pixels, validation_pixels).tolist()
    acc.cohen_kappa = cohen_kappa_score(control_pixels, validation_pixels)
    acc.accuracy_score = accuracy_score(control_pixels, validation_pixels)
    acc.save()

    # Store result in classifier.
    classifier.trained = File(io.BytesIO(pickle.dumps(clf)), name='trained')
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
    CHUNK_SIZE = 100
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
    # Get rasterlayer ids.
    if chunk.predictedlayer.composite_id:
        rasterlayer_lookup = chunk.predictedlayer.composite.rasterlayer_lookup
    else:
        rasterlayer_lookup = chunk.predictedlayer.sentineltile.rasterlayer_lookup
    # Predict tiles over this chunk's range.
    for tilex, tiley, tilez in list(tiles)[chunk.from_index:chunk.to_index]:
        # Get data from tiles for prediction.
        data = get_classifier_data(rasterlayer_lookup, tilez, tilex, tiley)
        if data is None:
            continue
        # Predict classes.
        predicted = chunk.predictedlayer.classifier.clf.predict(data).astype('uint8')
        # Write predicted pixels into a tile and store in DB.
        write_raster_tile(chunk.predictedlayer.rasterlayer_id, predicted, tilez, tilex, tiley, datatype=1)

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
            tile_data = [aggregate_tile(tile, target_dtype='uint8', discrete=True) for tile in tile_data]
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
                nodata_value=0,
                datatype=1,
            )
    pred.write('Finished building pyramid, prediction task completed.', pred.FINISHED)


def export_training_data(traininglayer_id, min_date, max_date):
    """
    Export training data to a file over a date range for monthly composites.
    """
    # Get composite list.
    composites = Composite.objects.filter(
        official=True,
        interval=Composite.MONTHLY,
        min_date__gte=min_date,
        max_date__lte=max_date,
    )

    # Get training layer.
    obj = TrainingLayer.objects.get(id=traininglayer_id)

    # Store initial composite id.
    original_composite_id = obj.trainingsample_set.first().composite.id

    # Loop through composites.
    for comp in composites:
        print('Exporting training matrix for', comp)
        # Update target composite layer.
        for sample in obj.trainingsample_set.all():
            sample.composite = comp
            sample.save()
        # Get training data.
        X, Y, PID = populate_training_matrix(obj)
        # Append class values to matrix.
        data = numpy.append(Y.reshape((len(Y), 1)), X, 1).astype('int64')
        # Append class names to matrix.
        names = numpy.chararray(Y.shape, itemsize=max(len(category_name) for category_name in obj.legend.values()))
        for category_dn, category_name in obj.legend.items():
            names[Y == int(category_dn)] = category_name
        data = numpy.append(names.reshape((len(names), 1)), data, 1)
        # Apend pixel ids to matrix.
        data = numpy.append(PID.reshape((len(PID), 1)).astype('int64'), data, 1)
        # Append header to matrix.
        header = numpy.array(['PixelId', 'ClassName', 'ClassDigitalNumber'] + [band.split('.jp2')[0] for band in CLASSIFY_BAND_NAMES])
        data = numpy.append(header.reshape((1, len(header))), data, 0)
        # Write data to csv file.
        csv_name = 'traininglayer-{}-{}.csv'.format(obj.id, comp.min_date)
        csv_path = os.path.join('/tmp/', csv_name)
        numpy.savetxt(csv_path, data, delimiter=',', fmt='%s')
        # Create training layer export instance.
        TrainingLayerExport.objects.create(
            traininglayer=obj,
            data=File(open(csv_path, 'rb'), name=csv_name)
        )

    # Restore original composite ids.
    for sample in obj.trainingsample_set.all():
        sample.composite_id = original_composite_id
        sample.save()
