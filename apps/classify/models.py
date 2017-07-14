from django.contrib.gis.db import models
from django.contrib.postgres.fields import HStoreField
from sentinel.models import SentinelTile, WorldLayerGroup
from sklearn import svm
from sklearn.ensemble import RandomForestClassifier
from sklearn.neural_network import MLPClassifier


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
        SVM: svm.SVC,
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
