import numpy
import pickle
from django.core.cache import cache
from sentinel import const
from classify.models import Classifier
from classify.tasks import BAND_NAMES


def clouds(stack):
    """
    Compute Cloud probabilities based on cloud classifier.
    """
    # Get classifier from cache.
    clf = cache.get('cloud_classifier')
    # If the classifier is not cached, get it from storage and cache it locally.
    if not clf:
        clf = pickle.loads(Classifier.objects.filter(name__icontains='cloud').first().trained.read())
        cache.set('cloud_classifier', clf, 6000)

    clf = pickle.loads(Classifier.objects.filter(name__icontains='cloud').first().trained.read())

    X = numpy.array([stack[name].ravel() for name in BAND_NAMES])
    cloud_probs = clf.predict(X.T).reshape(256, 256)

    cloud_probs[stack[const.BD2] == const.SENTINEL_NODATA_VALUE] = 3


    return cloud_probs
