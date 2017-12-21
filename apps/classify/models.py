import pickle

from raster.models import RasterLayer
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.svm import LinearSVC

from django.contrib.gis.db import models
from django.contrib.postgres.fields import HStoreField
from django.core.cache import cache
from sentinel.models import SentinelTile, WorldLayerGroup


class TrainingSample(models.Model):
    """
    Training Data for cloud classifiers.
    """
    sentineltile = models.ForeignKey(SentinelTile, null=True, blank=True, on_delete=models.CASCADE)
    worldlayergroup = models.ForeignKey(WorldLayerGroup, null=True, blank=True, on_delete=models.CASCADE)
    geom = models.PolygonField()
    category = models.CharField(max_length=100)
    value = models.IntegerField()

    def __str__(self):
        return '{0} - {1}'.format(self.category, self.worldlayergroup if self.worldlayergroup else self.sentineltile)


class Classifier(models.Model):
    """
    Pickled cloud classifier models.
    """
    SVM = 'svm'
    RF = 'rf'
    NN = 'nn'

    ALGORITHM_CHOICES = (
        (SVM, 'Support Vector Machines'),
        (RF, 'Random Forest'),
        (NN, 'Neural Network'),
    )

    ALGORITHM_CLASSES = {
        SVM: LinearSVC,
        RF: RandomForestClassifier,
        NN: MLPClassifier,
    }

    name = models.CharField(max_length=100)
    algorithm = models.CharField(max_length=10, choices=ALGORITHM_CHOICES)
    trained = models.FileField(upload_to='clouds/classifiers', blank=True, null=True)
    trainingsamples = models.ManyToManyField(TrainingSample)
    legend = HStoreField(default={}, editable=False)

    def __str__(self):
        return '{0} ({1})'.format(self.name, self.get_algorithm_display())

    @property
    def clf(self):
        # Create cache key for this classifier.
        cache_key = 'sentinel_classifier_{}'.format(self.id)
        # Get classifier from cache.
        clf = cache.get(cache_key)
        # If the classifier is not cached, get it from storage and cache it locally.
        if not clf:
            clf = pickle.loads(self.trained.read())
            cache.set(cache_key, clf, 6000)
        return clf


class PredictedLayer(models.Model):
    """
    A rasterlayer with prediction output from a classifier.
    """
    classifier = models.ForeignKey(Classifier, null=True, blank=True, on_delete=models.SET_NULL)
    sentineltile = models.ForeignKey(SentinelTile, null=True, blank=True, on_delete=models.SET_NULL)
    worldlayergroup = models.ForeignKey(WorldLayerGroup, null=True, blank=True, on_delete=models.SET_NULL)
    rasterlayer = models.ForeignKey(RasterLayer, blank=True, on_delete=models.CASCADE)
    log = models.TextField(default='')
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return 'Layer for {0} over {1}.'.format(
            self.classifier.name,
            self.worldlayergroup if self.worldlayergroup else self.sentineltile
        )

    def save(self, *args, **kwargs):
        # Create rasterlayer if it does not exist.
        if not hasattr(self, 'rasterlayer'):
            self.rasterlayer = RasterLayer.objects.create(
                name='Predicted layer CLF {0} {1} {2}'.format(
                    self.classifier_id,
                    'WL' if self.worldlayergroup else 'ST',
                    self.worldlayergroup_id if self.worldlayergroup else self.sentineltile_id,
                ),
                datatype=RasterLayer.CATEGORICAL,
            )
        super().save(*args, **kwargs)  # Call the "real" save() method.
