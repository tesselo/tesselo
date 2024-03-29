import datetime
import io
import json
import pickle
import zipfile

import numpy
from django.contrib.gis.db import models
from django.contrib.postgres.fields import ArrayField, HStoreField
from django.db.models import Max, Min
from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase
from raster.models import Legend, RasterLayer
from raster_aggregation.models import AggregationLayer

from classify.const import PIPELINE_ESTIMATOR_NAME, ZIP_ESTIMATOR_NAME, ZIP_PIPELINE_NAME
from sentinel.const import ZOOM_LEVEL_10M
from sentinel.models import Composite, SentinelTile
from sentinel.utils import populate_raster_metadata


class TrainingLayer(models.Model):
    """
    A group of training sample polygons and the extracted training pixels.
    """

    name = models.CharField(max_length=500)
    legend = HStoreField(default=dict, editable=False)
    continuous = models.BooleanField(default=False, help_text='Are the target values of this traininglayer continuous values? If false, its assumed to be discrete.')

    def __str__(self):
        return self.name


class TrainingSample(models.Model):
    """
    Training Data for cloud classifiers.
    """
    sentineltile = models.ForeignKey(SentinelTile, null=True, blank=True, on_delete=models.CASCADE)
    composite = models.ForeignKey(Composite, null=True, blank=True, on_delete=models.CASCADE)
    geom = models.PolygonField()
    category = models.CharField(max_length=100, default='', blank=True)
    value = models.FloatField()
    date = models.DateField(null=True, blank=True)
    traininglayer = models.ForeignKey(TrainingLayer, on_delete=models.CASCADE)
    attributes = HStoreField(default=dict)

    def __str__(self):
        return '{0} - {1}'.format(self.category, self.composite if self.composite else self.sentineltile)


class TrainingPixels(models.Model):
    """
    Training pixels for one composite over a training layer sample set.
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
    name = models.CharField(max_length=100)
    traininglayer = models.ForeignKey(TrainingLayer, blank=True, null=True, on_delete=models.SET_NULL)
    look_back_steps = models.PositiveIntegerField(default=0, help_text='Number of composite steps back from sample date should be included in training and predicting data collection. Ignored if zero.')
    band_names = models.CharField(max_length=500, default='B01,B02,B03,B04,B05,B06,B07,B08,B8A,B09,B11,B12', help_text='Comma-separated list of band names and layer ids. If an integer value is added, it is assumed to be a rasterlayer id that should be included in the export.')
    composites = models.ManyToManyField(Composite, blank=True, help_text='Is used as training data source if specified. If left blank, the original traininglayer pixels are used.')
    sentineltile = models.ForeignKey(SentinelTile, blank=True, null=True, on_delete=models.SET_NULL, help_text='Is used as training data source if specified. If left blank, the original traininglayer pixels are used.')
    training_all_touched = models.BooleanField(default=True, help_text='Sets the all_touched flag when rasterizing the training samples.')
    needs_large_instance = models.BooleanField(default=False)
    patch_size = models.IntegerField(default=100, help_text='Determines how many training sample geometries should be bundeled into a patch.')
    buffer = models.FloatField(default=0)
    flatten = models.BooleanField(default=True)
    collected_pixels = models.FileField(upload_to='clouds/trainingpixels', blank=True, null=True)
    status = models.CharField(max_length=20, choices=ST_STATUS_CHOICES, default=UNPROCESSED)
    log = models.TextField(blank=True, default='')

    def __str__(self):
        return '{} ({})'.format(self.name, self.status)

    def write(self, data, status=None):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        if status:
            self.status = status
        self.save()

    def unpack_collected_pixels(self):
        data = numpy.load(self.collected_pixels)
        if self.flatten:
            # Convert categories to dict.
            categories = {catkey: int(catval) for catkey, catval in data['categories']}
            return data['X'], data['Y'], data['PID'], data['SID'], categories
        else:
            return data


class TrainingPixelsPatch(models.Model):
    """
    Training pixels for one composite over a training layer sample set.
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
    trainingpixels = models.ForeignKey(TrainingPixels, on_delete=models.CASCADE)
    index_from = models.IntegerField()
    index_to = models.IntegerField()
    collected_pixels = models.FileField(upload_to='clouds/trainingpixels', blank=True, null=True)
    status = models.CharField(max_length=20, choices=ST_STATUS_CHOICES, default=UNPROCESSED)
    log = models.TextField(blank=True, default='')

    def __str__(self):
        return '{} | {} | {}'.format(self.id, self.trainingpixels.name, self.status)

    def write(self, data, status=None):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        if status:
            self.status = status
        self.save()


class Classifier(models.Model):
    """
    Pickled cloud classifier models.
    """
    SVM = 'svm'
    LSVM = 'lsvm'
    SVR = 'svr'
    LSVR = 'lsvr'
    RF = 'rf'
    RFR = 'rfr'
    NN = 'nn'
    NNR = 'nnr'
    KERAS = 'keras'
    KERAS_REGRESSOR = 'kerasr'

    ALGORITHM_CHOICES = (
        (SVM, 'Support Vector Machines'),
        (LSVM, 'Linear Support Vector Machines'),
        (RF, 'Random Forest'),
        (NN, 'Neural Network'),
        (SVR, 'Support Vector Machines Regressor'),
        (LSVR, 'Linear Support Vector Machines Regressor'),
        (RFR, 'Random Forest Regressor'),
        (NNR, 'Neural Network Regressor'),
        (KERAS, 'Keras Model'),
        (KERAS_REGRESSOR, 'Keras Model Regressor'),
    )

    ALGORITHM_MODULES = {
        SVM: ('svm', 'SVC'),
        LSVM: ('svm', 'LinearSVC'),
        SVR: ('svm', 'SVR'),
        LSVR: ('svm', 'LinearSVR'),
        RF: ('ensemble', 'RandomForestClassifier'),
        RFR: ('ensemble', 'RandomForestRegressor'),
        NN: ('neural_network', 'MLPClassifier'),
        NNR: ('neural_network', 'MLPRegressor'),
    }

    REGRESSORS = (SVR, LSVR, RFR, NNR, KERAS_REGRESSOR, )

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
    collected_pixels = models.FileField(upload_to='clouds/classifiers', blank=True, null=True)
    traininglayer = models.ForeignKey(TrainingLayer, blank=True, null=True, on_delete=models.SET_NULL)
    trainingpixels = models.ForeignKey(TrainingPixels, blank=True, null=True, on_delete=models.SET_NULL)
    splitfraction = models.FloatField(default=0, help_text='Fraction of pixels that should be reserved for validation.')
    split_by_polygon = models.BooleanField(default=False, help_text='Reserve pixels at the polygon level, i.e. keep a percentage of training polygons as verification data.')
    split_random_seed = models.PositiveIntegerField(null=True, blank=True, help_text='Fix random seed for train and test split to make verification more comparable.')
    auto_class_weights = models.BooleanField(default=False, help_text='Automatically compute class weights and use as fit parameters in Keras.')
    look_back_steps = models.PositiveIntegerField(default=0, help_text='Number of composite steps back from sample date should be included in training and predicting data collection. Ignored if zero.')
    band_names = models.CharField(max_length=500, default='B01,B02,B03,B04,B05,B06,B07,B08,B8A,B09,B11,B12', help_text='Comma-separated list of band names and layer ids. If an integer value is added, it is assumed to be a rasterlayer id that should be included in the export.')
    composites = models.ManyToManyField(Composite, blank=True, help_text='Is used as training data source if specified. If left blank, the original traininglayer pixels are used.', related_name='old_composite')
    sentineltile = models.ForeignKey(SentinelTile, blank=True, null=True, on_delete=models.SET_NULL, help_text='Is used as training data source if specified. If left blank, the original traininglayer pixels are used.')
    clf_args = models.TextField(default='{}', blank=True, help_text='Keyword arguments passed to the classifier. This will be ignored if clf_args is not a valid json string.')
    wrap_keras_with_sklearn = models.BooleanField(default=False, help_text='Wrap the keras models with a Sklearn Pipeline and RobustScaler. Ignored if not a Keras model.')
    keras_model_json = models.TextField(default='', blank=True, null=True, help_text='A Keras model definition string created by model.to_json().')
    needs_large_instance = models.BooleanField(default=False)
    training_all_touched = models.BooleanField(default=True, help_text='Sets the all_touched flag when rasterizing the training samples.')
    status = models.CharField(max_length=20, choices=ST_STATUS_CHOICES, default=UNPROCESSED)
    log = models.TextField(blank=True, default='')

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.name, self.get_algorithm_display(), self.status)

    _clf = None

    @property
    def clf(self):
        if self._clf is None:
            if self.is_keras:
                import h5py
                from tensorflow.keras.models import load_model
                with zipfile.ZipFile(io.BytesIO(self.trained.read()), 'r') as zf:
                    model = load_model(h5py.File(io.BytesIO(zf.read(ZIP_ESTIMATOR_NAME)), 'r'))
                    if self.wrap_keras_with_sklearn:
                        self._clf = pickle.loads(zf.read(ZIP_PIPELINE_NAME))
                        self._clf.named_steps[PIPELINE_ESTIMATOR_NAME].model = model
                    else:
                        self._clf = model
            else:
                self._clf = pickle.loads(self.trained.read())
        return self._clf

    def write(self, data, status=None):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        if status:
            self.status = status
        self.save()

    @property
    def is_regressor(self):
        return self.algorithm in self.REGRESSORS

    @property
    def is_keras(self):
        return self.algorithm in (self.KERAS, self.KERAS_REGRESSOR)

    @property
    def clf_args_dict(self):
        try:
            return json.loads(self.clf_args)
        except json.decoder.JSONDecodeError:
            return {}


class ClassifierAccuracy(models.Model):
    """
    Accuracy data for the classifier.
    """
    classifier = models.OneToOneField(Classifier, on_delete=models.CASCADE)
    accuracy_matrix = ArrayField(ArrayField(models.FloatField(), default=list), default=list)
    cohen_kappa = models.FloatField(default=0)
    accuracy_score = models.FloatField(default=0)
    rsquared = models.FloatField(default=0)

    def __str__(self):
        return '{} Accuracy {}'.format(
            self.classifier,
            self.rsquared if self.classifier.is_regressor else self.accuracy_score
        )


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

    SIEVE_CONNECTIVITY_4 = 4
    SIEVE_CONNECTIVITY_8 = 8
    SIEVE_CHOICES = (
        (SIEVE_CONNECTIVITY_4, SIEVE_CONNECTIVITY_4),
        (SIEVE_CONNECTIVITY_8, SIEVE_CONNECTIVITY_8),
    )
    name = models.CharField(max_length=500, default='', blank=True)
    classifier = models.ForeignKey(Classifier, null=True, blank=True, on_delete=models.SET_NULL)
    sentineltile = models.ForeignKey(SentinelTile, null=True, blank=True, on_delete=models.SET_NULL)
    composites = models.ManyToManyField(Composite, blank=True)
    aggregationlayer = models.ForeignKey(AggregationLayer, null=True, blank=True, on_delete=models.SET_NULL)
    rasterlayer = models.ForeignKey(RasterLayer, blank=True, on_delete=models.CASCADE)
    log = models.TextField(default='', blank=True)
    status = models.CharField(max_length=20, choices=ST_STATUS_CHOICES, default=UNPROCESSED)
    legend = models.ForeignKey(Legend, null=True, blank=True, on_delete=models.SET_NULL)
    min_date = models.DateField(null=True, blank=True, editable=False)
    max_date = models.DateField(null=True, blank=True, editable=False)
    chunk_size = models.IntegerField(default=100, help_text='Number of tiles to process per task. Reduce size for predictions with many composites.')

    sieve_threshold = models.IntegerField(default=0)
    sieve_connectivity = models.IntegerField(default=4, choices=SIEVE_CHOICES)
    sieve_parent = models.ForeignKey('classify.PredictedLayer', blank=True, null=True, on_delete=models.SET_NULL)

    store_class_probabilities = models.BooleanField(default=False)

    def __str__(self):
        if self.name:
            return '{} | {}'.format(self.name, self.status)
        else:
            if self.classifier and self.classifier.is_keras:
                using = ''
            elif self.composites.count():
                using = 'using {} composites'.format(self.composites.count())
            elif self.sentineltile:
                using = 'using {}'.format(self.sentineltile)
            else:
                using = ''

            agglayer = self.aggregationlayer.name if self.aggregationlayer else ''

            return '{} over {} {} | {}.'.format(
                self.classifier,
                agglayer,
                using,
                self.status,
            )

    def save(self, *args, **kwargs):
        if not hasattr(self, 'rasterlayer'):
            # Create rasterlayer if it does not exist.
            self.rasterlayer = RasterLayer.objects.create(
                name='PredictedLayer {0} CLF {1}'.format(
                    self.id,
                    self.classifier_id,
                ),
                datatype=RasterLayer.CATEGORICAL,
                max_zoom=ZOOM_LEVEL_10M,
                legend_id=self.legend_id if hasattr(self, 'legend') else None,
            )
            populate_raster_metadata(self.rasterlayer)
        elif hasattr(self, 'legend'):
            # Update legend if necessary.
            if self.rasterlayer.legend_id != self.legend_id:
                self.rasterlayer.legend_id = self.legend_id
                self.rasterlayer.save()

        if self.sentineltile:
            self.min_date = self.sentineltile.collected.date()
            self.max_date = self.sentineltile.collected.date()

        super().save(*args, **kwargs)

    def write(self, data, status=None):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        if status:
            self.status = status
        self.save()


@receiver(m2m_changed, sender=PredictedLayer.composites.through, weak=False, dispatch_uid="update_min_max_date_range_on_predictedlayer")
def update_min_max_date_range_on_predictedlayer(sender, instance, **kwargs):
    """
    Automatically update min and max dates based on associated composites or
    sentinel tile.
    """
    if instance.composites.count():
        instance.min_date = instance.composites.aggregate(Min('min_date'))['min_date__min']
        instance.max_date = instance.composites.aggregate(Max('max_date'))['max_date__max']
    elif instance.sentineltile:
        instance.min_date = instance.sentineltile.collected.date()
        instance.max_date = instance.sentineltile.collected.date()
    else:
        instance.min_date = None
        instance.max_date = None

    instance.save()


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
