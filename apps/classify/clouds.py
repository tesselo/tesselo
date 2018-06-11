import numpy
from raster.tiles.const import WEB_MERCATOR_TILESIZE

from classify.models import Classifier
from classify.tasks import CLASSIFY_BAND_NAMES
from sentinel import const


def clouds(stack):
    """
    Compute Cloud probabilities based on cloud classifier.
    """
    # Get classifier.
    clf = Classifier.objects.filter(name__icontains='cloud').first().clf

    # Construct the prediction input matrix.
    X = numpy.array([stack[name].ravel() for name in CLASSIFY_BAND_NAMES])

    # Predict based on data and reshape back to tile format.
    cloud_probs = clf.predict(X.T).reshape(WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE)

    # Get the nodata mask from a low resolution band, and set all
    # nodata values to the highest value, so that they are never
    # selected if there is any pixel with data.
    cloud_probs[stack[const.BD1] == const.SENTINEL_NODATA_VALUE] = 4

    return cloud_probs
