import datetime
import importlib
import io
import pickle

import numpy
from raster.rasterize import rasterize
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.lookup import get_raster_tile
from raster.tiles.utils import tile_bounds, tile_index_range, tile_scale

from classify.models import Classifier, PredictedLayer
from django.contrib.gis.gdal import GDALRaster
from django.core.files import File
from sentinel import ecs
from sentinel.utils import aggregate_tile, get_composite_tile_indices, get_sentinel_tile_indices, write_raster_tile

ZOOM = 14

SCALE = tile_scale(ZOOM)

PIXELTYPE = 2

CLASSIFY_BAND_NAMES = (
    'B02.jp2', 'B03.jp2', 'B04.jp2', 'B05.jp2', 'B06.jp2', 'B07.jp2', 'B08.jp2',
    'B8A.jp2', 'B09.jp2', 'B10.jp2', 'B11.jp2', 'B12.jp2',
)


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


def train_sentinel_classifier(classifier_id):
    """
    Trains a classifier based on the registered tiles and sample data.
    """
    # Get classifier model.
    classifier = Classifier.objects.get(pk=classifier_id)
    # Create numpy arrays holding training data.
    NUMBER_OF_BANDS = len(CLASSIFY_BAND_NAMES)
    X = numpy.empty(shape=(0, NUMBER_OF_BANDS))
    Y = numpy.empty(shape=(0,))
    # Dictionary for categories.
    categories = {}
    # Loop through training tiles to build training set.
    for sample in classifier.trainingsamples.all():
        # Check for consistency in training samples
        if sample.category in categories:
            if sample.value != categories[sample.category]:
                raise ValueError('Found different values for same category.')
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

    # Instanciate and fit the classifier.
    clf_mod, clf_class = classifier.ALGORITHM_MODULES[classifier.algorithm]
    clf_mod = importlib.import_module('sklearn.' + clf_mod)
    clf = getattr(clf_mod, clf_class)()
    clf.fit(X, Y)

    # Store result in classifier.
    classifier.legend = categories
    classifier.trained = File(io.BytesIO(pickle.dumps(clf)), name='trained')
    classifier.save()


def get_prediction_index_range(pred, zoom=ZOOM):
    # Get tile range for compositeband or sentineltile for this prediction.
    if pred.composite:
        return get_composite_tile_indices(pred.composite, zoom)
    else:
        return get_sentinel_tile_indices(pred.sentineltile, zoom)


def predict_sentinel_layer(predicted_layer_id):
    """
    Use a classifier to predict data onto a rasterlayer. The PredictedLayer
    model is the mediator.
    """
    pred = PredictedLayer.objects.get(id=predicted_layer_id)
    pred.chunks_done = 0
    pred.log = '[{0}] Started predicting layer.'.format(datetime.datetime.now())
    pred.save()

    # Get tile range for compositeband or sentineltile for this prediction.
    tiles = get_prediction_index_range(pred)

    # Push tasks for sentinel chunks.
    counter = 0
    chunk_counter = 0
    CHUNK_SIZE = 100
    for tile_index in tiles:
        counter += 1
        if counter % CHUNK_SIZE == 0:
            chunk_counter += 1
            ecs.predict_sentinel_chunk(pred.id, counter - CHUNK_SIZE, counter)
    # Push the remaining index range as well.
    rest = counter % 50
    if rest:
        chunk_counter += 1
        ecs.predict_sentinel_chunk(pred.id, counter - rest, counter)
    # Save number of jobs to be done.
    pred.refresh_from_db()
    pred.chunks_count = chunk_counter
    pred.save()


def predict_sentinel_chunk(predicted_layer_id, from_idx, to_idx):
    """
    Predict over a group of tiles.
    """
    pred = PredictedLayer.objects.get(id=predicted_layer_id)
    tiles = get_prediction_index_range(pred)
    from_idx = int(from_idx)
    to_idx = int(to_idx)

    if pred.composite:
        rasterlayer_lookup = pred.composite.rasterlayer_lookup
    else:
        rasterlayer_lookup = pred.sentineltile.rasterlayer_lookup

    for tilex, tiley, tilez in list(tiles)[from_idx:to_idx]:
        # Get data from tiles for prediction.
        data = get_classifier_data(rasterlayer_lookup, tilez, tilex, tiley)
        if data is None:
            continue
        # Predict classes.
        predicted = pred.classifier.clf.predict(data).astype('uint8')
        # Write predicted pixels into a tile and store in DB.
        write_raster_tile(pred.rasterlayer_id, predicted, tilez, tilex, tiley, datatype=1)

    # Log progress, update chunks done count.
    pred.refresh_from_db()
    pred.log += '\n[{0}] Finished chunks from {1} to {2}'.format(datetime.datetime.now(), from_idx, to_idx)
    pred.chunks_done += 1
    pred.save()

    # If all chunks have completed, push pyramid build job.
    if pred.chunks_count > 0 and pred.chunks_done == pred.chunks_count:
        ecs.build_predicted_pyramid(predicted_layer_id)


def build_predicted_pyramid(predicted_layer_id):
    """
    Build an overview stack over a predicted layer.
    """
    pred = PredictedLayer.objects.get(id=predicted_layer_id)
    # Loop through the tiles in each zoom level, bottom up.
    for tilez in range(ZOOM - 1, -1, -1):
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
            tile_data = [aggregate_tile(tile, numpy.uint8) for tile in tile_data]
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
