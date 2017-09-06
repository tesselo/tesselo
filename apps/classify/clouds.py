import pickle

import numpy
from raster.tiles.const import WEB_MERCATOR_TILESIZE

from classify.models import Classifier
from classify.tasks import BAND_NAMES
# from django.core.cache import cache
from sentinel import const


def clouds(stack):
    """
    Compute Cloud probabilities based on cloud classifier.
    """
    # Get classifier (should use cache in production).
    clf = pickle.loads(Classifier.objects.filter(name__icontains='cloud').first().trained.read())
    # clf = cache.get('cloud_classifier')
    # If the classifier is not cached, get it from storage and cache it locally.
    # if not clf:
    #     clf = pickle.loads(Classifier.objects.filter(name__icontains='cloud').first().trained.read())
    #     cache.set('cloud_classifier', clf, 6000)

    # Construct the prediction input matrix.
    X = numpy.array([stack[name].ravel() for name in BAND_NAMES])

    # Predict based on data and reshape back to tile format.
    cloud_probs = clf.predict(X.T).reshape(WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE)

    # Get the nodata mask from a low resolution band, and set all
    # nodata values to the highest value, so that they are never
    # selected if there is any pixel with data.
    cloud_probs[stack[const.BD1] == const.SENTINEL_NODATA_VALUE] = 4

    return cloud_probs
