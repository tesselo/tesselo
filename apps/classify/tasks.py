import datetime
import importlib
import io
import pickle

import numpy
from celery import task
from raster.models import RasterTile
from raster.rasterize import rasterize
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.lookup import get_raster_tile
from raster.tiles.utils import tile_bounds, tile_index_range, tile_scale

from classify.models import Classifier, PredictedLayer
from django.contrib.gis.gdal import GDALRaster
from django.core.files import File
from sentinel.utils import get_composite_tile_indices, get_sentinel_tile_indices, write_raster_tile

ZOOM = 14

SCALE = tile_scale(ZOOM)

PIXELTYPE = 2

BAND_NAMES = (
    'B01.jp2', 'B02.jp2', 'B03.jp2', 'B04.jp2', 'B05.jp2', 'B06.jp2',
    'B07.jp2', 'B08.jp2', 'B8A.jp2', 'B09.jp2', 'B10.jp2', 'B11.jp2',
    'B12.jp2',
)


def get_classifier_data(rasterlayer_lookup, tilez, tilex, tiley):
    """
    Builds the 13 band training tile file for a training tile instance.
    """
    # Get data for a tile of this scene.
    result = []
    for band in BAND_NAMES:
        layer_id = rasterlayer_lookup.get(band)
        tile = RasterTile.objects.filter(
            tilex=tilex,
            tiley=tiley,
            tilez=tilez,
            rasterlayer_id=layer_id,
        )
        tile = get_raster_tile(layer_id, tilez=tilez, tilex=tilex, tiley=tiley)
        if not tile:
            return
        result.append(tile.bands[0].data().ravel())

    return numpy.array(result).T


@task
def train_sentinel_classifier(classifier_id):
    """
    Trains a classifier based on the registered tiles and sample data.
    """
    # Get classifier model.
    classifier = Classifier.objects.get(pk=classifier_id)
    # Create numpy arrays holding training data.
    X = numpy.empty(shape=(0, 13))
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
                sample_values = numpy.array([sample.value] * sum(selector))
                # Add sample values to dependent variable.
                Y = numpy.hstack([sample_values, Y])
                # Use selector to pick sample pixels over geom.
                data = data[selector]
                # Add explanatory variables to stack.
                X = numpy.vstack([data, X])

    # Instanciate and fit the classifier.
    clf_mod, clf_class = classifier.ALGORITHM_MODULES[classifier.algorithm]()
    clf_mod = importlib.import_module('sklearn.' + clf_mod)
    clf = getattr(clf_mod, clf_class)()
    clf.fit(X, Y)

    # Store result in classifier.
    classifier.legend = categories
    classifier.trained = File(io.BytesIO(pickle.dumps(clf)), name='trained')
    classifier.save()


@task
def predict_sentinel_layer(predicted_layer_id):
    """
    Use a classifier to predict data onto a rasterlayer. The PredictedLayer
    model is the mediator.
    """
    pred = PredictedLayer.objects.get(id=predicted_layer_id)
    pred.log = '[{0}] Started predicting layer.'.format(datetime.datetime.now())
    pred.save()
    # Get tile range for compositeband or sentineltile for this prediction.
    if pred.composite:
        tiles = get_composite_tile_indices(pred.composite, ZOOM)
        rasterlayer_lookup = pred.composite.rasterlayer_lookup
    else:
        tiles = get_sentinel_tile_indices(pred.sentineltile, ZOOM)
        rasterlayer_lookup = pred.sentineltile.rasterlayer_lookup

    counter = 0
    chunks = []
    for tile_index in tiles:
        chunks.append(tile_index)
        counter += 1
        if counter % 50 == 0:
            predict_sentinel_chunks.delay(pred.id, rasterlayer_lookup, chunks)
            chunks = []


@task
def predict_sentinel_chunks(predicted_layer_id, rasterlayer_lookup, chunks):
    """
    Predict over a group of tiles.
    """
    pred = PredictedLayer.objects.get(id=predicted_layer_id)
    for tilex, tiley, tilez in chunks:
        # Get data from tiles for prediction.
        data = get_classifier_data(rasterlayer_lookup, tilez, tilex, tiley)
        if data is None:
            continue
        # Predict classes.
        predicted = pred.classifier.clf.predict(data).astype('uint8')
        # Write predicted pixels into a tile and store in DB.
        write_raster_tile(pred.rasterlayer_id, predicted, tilez, tilex, tiley, datatype=1)

    pred.refresh_from_db()
    pred.log += '\n[{0}] Finished chunks from {1} to {2}'.format(datetime.datetime.now(), chunks[0], chunks[-1])
    pred.save()
