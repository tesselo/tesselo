import io
import pickle

import numpy
from celery import task
from raster.models import RasterTile
from raster.rasterize import rasterize
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import get_raster_tile, tile_bounds, tile_index_range, tile_scale

from classify.models import Classifier
from django.contrib.gis.gdal import GDALRaster
from django.core.files import File
from sklearn.metrics import confusion_matrix

ZOOM = 14

SCALE = tile_scale(ZOOM)

PIXELTYPE = 2

tile_list = [
    # ('tiles/29/S/PB/2017/3/23/0/', 7835, 6308),
    # ('tiles/29/S/NC/2017/3/6/1/', 7835, 6308),
    # ('tiles/29/S/PC/2017/3/16/0/', 7835, 6308),
    # ('tiles/29/S/NB/2017/3/6/1/', 7835, 6308),
]

BAND_NAMES = (
    'B01.jp2', 'B02.jp2', 'B03.jp2', 'B04.jp2', 'B05.jp2', 'B06.jp2',
    'B07.jp2', 'B08.jp2', 'B8A.jp2', 'B09.jp2', 'B10.jp2', 'B11.jp2',
    'B12.jp2',
)


def get_training_data(sentineltile, tilez, tilex, tiley):
    """
    Builds the 13 band training tile file for a training tile instance.
    """
    # Get data for a tile of this scene.
    result = []
    for band in BAND_NAMES:
        band = sentineltile.sentineltileband_set.get(band=band)
        tile = RasterTile.objects.filter(
            tilex=tilex,
            tiley=tiley,
            tilez=tilez,
            rasterlayer_id=band.layer_id,
        )
        tile = get_raster_tile(band.layer_id, tilez=tilez, tilex=tilex, tiley=tiley)
        if not tile:
            return
        result.append(tile.bands[0].data().ravel())

    return numpy.array(result)


@task
def train_cloud_classifier(classifier_id):
    """
    Trains a classifier based on the registered tiles and sample data.
    """
    # Get classifier model.
    classifier = Classifier.objects.get(pk=classifier_id)
    # Create numpy arrays holding training data.
    X = numpy.empty(shape=(13, 0))
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
                # Get stacked tile data for this tile.
                data = get_training_data(sample.sentineltile, ZOOM, tilex, tiley)
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
                # Use selector to pick independent sample pixels.
                data = data[:, selector]
                # Add explanatory variables to stack.
                X = numpy.hstack([data, X])

    # Reshape the data to fit the classifier input needs.
    X = X.T
    Y = Y.T.ravel()
    # Instanciate and fit the classifier.
    clf = classifier.ALGORITHM_CLASSES[classifier.algorithm]()
    clf.fit(X, Y)
    # Store result in classifier.
    classifier.legend = categories
    classifier.trained = File(io.BytesIO(pickle.dumps(clf)), name='trained')
    classifier.save()
