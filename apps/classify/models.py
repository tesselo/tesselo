import pickle

from raster.models import RasterLayer
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.svm import LinearSVC

from django.contrib.gis.db import models
from django.contrib.postgres.fields import HStoreField
from sentinel.models import Composite, SentinelTile


class TrainingSample(models.Model):
    """
    Training Data for cloud classifiers.
    """
    sentineltile = models.ForeignKey(SentinelTile, null=True, blank=True, on_delete=models.CASCADE)
    composite = models.ForeignKey(Composite, null=True, blank=True, on_delete=models.CASCADE)
    geom = models.PolygonField()
    category = models.CharField(max_length=100)
    value = models.IntegerField()

    def __str__(self):
        return '{0} - {1}'.format(self.category, self.composite if self.composite else self.sentineltile)


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
        return pickle.loads(self.trained.read())


class PredictedLayer(models.Model):
    """
    A rasterlayer with prediction output from a classifier.
    """
    classifier = models.ForeignKey(Classifier, null=True, blank=True, on_delete=models.SET_NULL)
    sentineltile = models.ForeignKey(SentinelTile, null=True, blank=True, on_delete=models.SET_NULL)
    composite = models.ForeignKey(Composite, null=True, blank=True, on_delete=models.SET_NULL)
    rasterlayer = models.ForeignKey(RasterLayer, blank=True, on_delete=models.CASCADE)
    log = models.TextField(default='')
    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return 'Layer for {0} over {1}.'.format(
            self.classifier.name,
            self.composite if self.composite else self.sentineltile
        )

    def save(self, *args, **kwargs):
        # Create rasterlayer if it does not exist.
        if not hasattr(self, 'rasterlayer'):
            self.rasterlayer = RasterLayer.objects.create(
                name='Predicted layer CLF {0} {1} {2}'.format(
                    self.classifier_id,
                    'WL' if self.composite else 'ST',
                    self.composite_id if self.composite else self.sentineltile_id,
                ),
                datatype=RasterLayer.CATEGORICAL,
            )
        super().save(*args, **kwargs)  # Call the "real" save() method.
