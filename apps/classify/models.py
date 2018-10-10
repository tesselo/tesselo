import datetime
import pickle

from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase
from raster.models import RasterLayer
from raster_aggregation.models import AggregationLayer

from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField, HStoreField
from django.db.models.signals import post_save
from django.dispatch import receiver
from sentinel.const import ZOOM_LEVEL_10M
from sentinel.models import Composite, SentinelTile
from sentinel.utils import populate_raster_metadata


class TrainingLayer(models.Model):
    """
    A group of training sample polygons and the extracted training pixels.
    """
    name = models.CharField(max_length=500)
    legend = HStoreField(default={}, editable=False)

    def __str__(self):
        return self.name

    class Meta:
        permissions = (
            ('view_traininglayer', 'View training layer'),
        )


class TrainingLayerExport(models.Model):
    """
    Export training pixels to files and store permanently.
    """
    traininglayer = models.ForeignKey(TrainingLayer, on_delete=models.CASCADE)
    data = models.FileField(upload_to='clouds/traininglayer_exports')
    created = models.DateTimeField(auto_now=True)

    def __str__(self):
        return '{} {}'.format(self.traininglayer.name, self.created)


class TrainingSample(models.Model):
    """
    Training Data for cloud classifiers.
    """
    sentineltile = models.ForeignKey(SentinelTile, null=True, blank=True, on_delete=models.CASCADE)
    composite = models.ForeignKey(Composite, null=True, blank=True, on_delete=models.CASCADE)
    geom = models.PolygonField()
    category = models.CharField(max_length=100)
    value = models.IntegerField()
    traininglayer = models.ForeignKey(TrainingLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} - {1}'.format(self.category, self.composite if self.composite else self.sentineltile)

    class Meta:
        permissions = (
            ('view_trainingsample', 'View training sample'),
        )


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

    ALGORITHM_MODULES = {
        SVM: ('svm', 'LinearSVC'),
        RF: ('ensemble', 'RandomForestClassifier'),
        NN: ('neural_network', 'MLPClassifier'),
    }

    UNPROCESSED = 'Unprocessed'
    PENDING = 'Pending'
    PROCESSING = 'Processing'
    FINISHED = 'Finished'
    FAILED = 'Failed'
    ST_STATUS_CHOICES = (
        (UNPROCESSED, UNPROCESSED),
        (PENDING, PENDING),
        (PROCESSING, PROCESSING),
        (FINISHED, FINISHED),
        (FAILED, FAILED),
    )

    name = models.CharField(max_length=100)
    algorithm = models.CharField(max_length=10, choices=ALGORITHM_CHOICES)
    trained = models.FileField(upload_to='clouds/classifiers', blank=True, null=True)
    traininglayer = models.ForeignKey(TrainingLayer, blank=True, null=True, on_delete=models.SET_NULL)
    splitfraction = models.FloatField(default=0, help_text='Fraction of pixels that should be reserved for validation.')
    band_names = models.CharField(max_length=500, default='B01,B02,B03,B04,B05,B06,B07,B08,B8A,B09,B11,B12', help_text='Comma-separated list of band names and layer ids. If an integer value is added, it is assumed to be a rasterlayer id that should be included in the export.')
    composite = models.ForeignKey(Composite, blank=True, null=True, on_delete=models.SET_NULL, help_text='Is used as training data source if specified. If left blank, the original traininglayer pixels are used.')
    sentineltile = models.ForeignKey(SentinelTile, blank=True, null=True, on_delete=models.SET_NULL, help_text='Is used as training data source if specified. If left blank, the original traininglayer pixels are used..')
    clf_args = HStoreField(default={}, blank=True, help_text='Keyword Arguments passed to the classifier.')
    needs_large_instance = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=ST_STATUS_CHOICES, default=UNPROCESSED)
    log = models.TextField(blank=True, default='')

    def __str__(self):
        return '{0} ({1})'.format(self.name, self.get_algorithm_display())

    class Meta:
        permissions = (
            ('view_classifier', 'View classifier'),
        )

    _clf = None

    @property
    def clf(self):
        if self._clf is None:
            self._clf = pickle.loads(self.trained.read())
        return self._clf

    def write(self, data, status=None):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        if status:
            self.status = status
        self.save()


class ClassifierAccuracy(models.Model):
    """
    Accuracy data for the classifier.
    """
    classifier = models.OneToOneField(Classifier, on_delete=models.CASCADE)
    accuracy_matrix = ArrayField(ArrayField(models.FloatField(), default=[]), default=[])
    cohen_kappa = models.FloatField(default=0)
    accuracy_score = models.FloatField(default=0)

    def __str__(self):
        return '{} Accuracy {}'.format(self.classifier, self.accuracy_score)


class PredictedLayer(models.Model):
    """
    A rasterlayer with prediction output from a classifier.
    """
    UNPROCESSED = 'Unprocessed'
    PENDING = 'Pending'
    PROCESSING = 'Processing'
    FINISHED = 'Finished'
    FAILED = 'Failed'
    ST_STATUS_CHOICES = (
        (UNPROCESSED, UNPROCESSED),
        (PENDING, PENDING),
        (PROCESSING, PROCESSING),
        (FINISHED, FINISHED),
        (FAILED, FAILED),
    )
    classifier = models.ForeignKey(Classifier, null=True, blank=True, on_delete=models.SET_NULL)
    sentineltile = models.ForeignKey(SentinelTile, null=True, blank=True, on_delete=models.SET_NULL)
    composite = models.ForeignKey(Composite, null=True, blank=True, on_delete=models.SET_NULL)
    aggregationlayer = models.ForeignKey(AggregationLayer, null=True, blank=True, on_delete=models.SET_NULL)
    rasterlayer = models.ForeignKey(RasterLayer, blank=True, on_delete=models.CASCADE)
    log = models.TextField(default='', blank=True)
    status = models.CharField(max_length=20, choices=ST_STATUS_CHOICES, default=UNPROCESSED)

    def __str__(self):
        return 'Layer for {0} over {1}.'.format(
            self.classifier,
            self.composite if self.composite else self.sentineltile
        )

    class Meta:
        permissions = (
            ('view_predictedlayer', 'View predicted layer'),
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
                max_zoom=ZOOM_LEVEL_10M,
            )
            populate_raster_metadata(self.rasterlayer)
        super().save(*args, **kwargs)  # Call the "real" save() method.

    def write(self, data, status=None):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        if status:
            self.status = status
        self.save()


class PredictedLayerChunk(models.Model):
    UNPROCESSED = 'Unprocessed'
    PENDING = 'Pending'
    PROCESSING = 'Processing'
    FINISHED = 'Finished'
    FAILED = 'Failed'
    PLC_STATUS_CHOICES = (
        (UNPROCESSED, UNPROCESSED),
        (PENDING, PENDING),
        (PROCESSING, PROCESSING),
        (FINISHED, FINISHED),
        (FAILED, FAILED),
    )
    predictedlayer = models.ForeignKey(PredictedLayer, on_delete=models.CASCADE)
    from_index = models.IntegerField()
    to_index = models.IntegerField()
    status = models.CharField(choices=PLC_STATUS_CHOICES, default=UNPROCESSED, max_length=100)

    def __str__(self):
        return 'Chunk Range {}-{} for Predictedlayer {} ({})'.format(
            self.from_index,
            self.to_index,
            self.predictedlayer_id,
            self.status,
        )


class TrainingLayerUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(TrainingLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class TrainingLayerGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(TrainingLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicTrainingLayer(models.Model):

    traininglayer = models.OneToOneField(TrainingLayer, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.traininglayer, 'public' if self.public else 'private')


@receiver(post_save, sender=TrainingLayer, weak=False, dispatch_uid="create_traininglayer_public_object")
def create_traininglayer_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public traininglayer object.
    """
    if created:
        PublicTrainingLayer.objects.create(traininglayer=instance)


class TrainingSampleUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(TrainingSample, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class TrainingSampleGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(TrainingSample, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicTrainingSample(models.Model):

    trainingsample = models.OneToOneField(TrainingSample, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.trainingsample, 'public' if self.public else 'private')


@receiver(post_save, sender=TrainingSample, weak=False, dispatch_uid="create_trainingsample_public_object")
def create_trainingsample_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public trainingsample object.
    """
    if created:
        PublicTrainingSample.objects.create(trainingsample=instance)


class ClassifierUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(Classifier, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class ClassifierGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(Classifier, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicClassifier(models.Model):

    classifier = models.OneToOneField(Classifier, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.classifier, 'public' if self.public else 'private')


@receiver(post_save, sender=Classifier, weak=False, dispatch_uid="create_classifier_public_object")
def create_classifier_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public classifier object.
    """
    if created:
        PublicClassifier.objects.create(classifier=instance)


class PredictedLayerUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(PredictedLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class PredictedLayerGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(PredictedLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicPredictedLayer(models.Model):

    predictedlayer = models.OneToOneField(PredictedLayer, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.predictedlayer, 'public' if self.public else 'private')


@receiver(post_save, sender=PredictedLayer, weak=False, dispatch_uid="create_predictedlayer_public_object")
def create_predictedlayer_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public predictedlayer object.
    """
    if created:
        PublicPredictedLayer.objects.create(predictedlayer=instance)
