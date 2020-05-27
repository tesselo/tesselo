import datetime

from raster_aggregation.models import AggregationArea, AggregationLayer, ValueCountResult

from classify.models import PredictedLayer
from django.contrib.postgres.fields import HStoreField
from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver
from sentinel.models import Composite


class ReportSchedule(models.Model):
    """
    Schedule automatic aggregation over an aggregationlayer using every
    combination of the formulas, composites, and predicted layers specified.
    """
    name = models.CharField(max_length=200, default='')
    aggregationlayers = models.ManyToManyField(AggregationLayer)
    formulas = models.ManyToManyField('formulary.Formula')
    composites = models.ManyToManyField(Composite)
    predictedlayers = models.ManyToManyField(PredictedLayer)
    active = models.BooleanField(default=False)

    def __str__(self):
        return '{} | {} | {}'.format(self.id, self.name, 'Active' if self.active else 'Deactivated')


class ReportScheduleTask(models.Model):
    """
    Track one long running async task to compute aggregation values.
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

    aggregationlayer = models.ForeignKey(AggregationLayer, on_delete=models.CASCADE)
    formula = models.ForeignKey('formulary.Formula', on_delete=models.CASCADE, blank=True, null=True)
    composite = models.ForeignKey(Composite, on_delete=models.CASCADE, blank=True, null=True)
    predictedlayer = models.ForeignKey(PredictedLayer, on_delete=models.CASCADE, blank=True, null=True)

    status = models.CharField(max_length=20, choices=ST_STATUS_CHOICES, default=UNPROCESSED)
    log = models.TextField(default='', blank=True)

    def __str__(self):
        return '{} | Agg {}, Comp {}, Form {}, Pred {}'.format(
            self.id,
            self.aggregationlayer,
            self.composite,
            self.formula,
            self.predictedlayer,
        )

    def write(self, data, status=None):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        if status:
            self.status = status
        self.save()


class ReportAggregation(models.Model):
    """
    Aggregate Sentinel-2 data by formula and aggregation area.
    """

    ZOOM = 14
    VALUECOUNT_ROUNDING_DIGITS = 7

    formula = models.ForeignKey('formulary.Formula', on_delete=models.CASCADE, blank=True, null=True, help_text='Leave empty for predicted layers.')
    aggregationlayer = models.ForeignKey(AggregationLayer, on_delete=models.CASCADE)
    aggregationarea = models.ForeignKey(AggregationArea, on_delete=models.CASCADE)

    composite = models.ForeignKey(Composite, on_delete=models.CASCADE, blank=True, null=True)
    predictedlayer = models.ForeignKey(PredictedLayer, on_delete=models.CASCADE, blank=True, null=True)

    valuecountresult = models.OneToOneField(ValueCountResult, on_delete=models.CASCADE, blank=True)

    min_date = models.DateField(null=True, blank=True, editable=False, db_index=True)
    max_date = models.DateField(null=True, blank=True, editable=False, db_index=True)

    value = HStoreField(default=dict, db_index=True)
    value_percentage = HStoreField(default=dict, db_index=True)

    stats_min = models.FloatField(editable=False, blank=True, null=True, db_index=True)
    stats_max = models.FloatField(editable=False, blank=True, null=True, db_index=True)
    stats_avg = models.FloatField(editable=False, blank=True, null=True, db_index=True)
    stats_std = models.FloatField(editable=False, blank=True, null=True, db_index=True)

    stats_cumsum_t0 = models.FloatField(editable=False, blank=True, null=True, help_text='Nr of pixels counted.')
    stats_cumsum_t1 = models.FloatField(editable=False, blank=True, null=True, help_text='Sum of pixel values.')
    stats_cumsum_t2 = models.FloatField(editable=False, blank=True, null=True, help_text='Sum of squares of pixel values.')

    stats_percentage_covered = models.FloatField(editable=False, blank=True, null=True, help_text='Percentage of area covered by valid pixels.')

    def __str__(self):
        dat = '{}'.format(self.id)
        if hasattr(self, 'aggregationlayer') and self.aggregationlayer:
            dat += ' | {}'.format(self.aggregationlayer.name)
        if hasattr(self, 'composite') and self.composite:
            dat += ' | {}'.format(self.composite.name)
        if hasattr(self, 'formula') and self.formula:
            dat += ' | {}'.format(self.formula.name)
        if hasattr(self, 'predictedlayer') and self.predictedlayer:
            dat += ' | Pred {}'.format(self.predictedlayer.id)
        return dat

    def get_valuecount(self):
        # Get data for valuecount result update.
        if self.composite:
            formula = self.formula.formula
            range_min = self.formula.min_val
            range_max = self.formula.max_val
            layer_names = {
                key.replace('.jp2', '').replace('0', ''): val for key, val in self.composite.rasterlayer_lookup.items()
            }
            # Only keep bands that are present in formula.
            layer_names = {key: val for key, val in layer_names.items() if key in formula}
            # Add predictedlayer keys to lookup.
            for pred in self.formula.predictedlayerformula_set.all():
                layer_names[pred.key] = pred.predictedlayer.rasterlayer_id
        elif self.predictedlayer_id:
            # Simple formula for predictedlayers.
            formula = 'x'
            layer_names = {'x': self.predictedlayer.rasterlayer_id}
            range_min = None
            range_max = None
        else:
            raise ValueError('Specify Composite or PredictedLayer.')

        # Remove existing valuecounts.
        if hasattr(self, 'valuecountresult'):
            self.valuecountresult.delete()

        # Setup new valuecount without storing it yet.
        return ValueCountResult(
            layer_names=layer_names,
            formula=formula,
            range_min=range_min,
            range_max=range_max,
            zoom=self.ZOOM,
            aggregationarea=self.aggregationarea,
            units='acres',
            grouping='discrete' if self.predictedlayer_id else 'continuous',
        )

    def copy_valuecount(self):
        # Copy the data to the ReportAggregation.
        self.value = self.valuecountresult.value
        self.stats_min = self.valuecountresult.stats_min
        self.stats_max = self.valuecountresult.stats_max
        self.stats_avg = self.valuecountresult.stats_avg
        self.stats_std = self.valuecountresult.stats_std
        self.stats_cumsum_t0 = self.valuecountresult.stats_cumsum_t0
        self.stats_cumsum_t1 = self.valuecountresult.stats_cumsum_t1
        self.stats_cumsum_t2 = self.valuecountresult.stats_cumsum_t2

        # Compute percentage by value.
        valsum = sum([float(val) for key, val in self.valuecountresult.value.items()])
        self.value_percentage = {key: str(round(float(val) / valsum, self.VALUECOUNT_ROUNDING_DIGITS)) for key, val in self.valuecountresult.value.items()}


@receiver(post_delete, sender=ReportAggregation, weak=False, dispatch_uid="remove_valuecount_before_delete")
def check_change_on_formula(sender, instance, **kwargs):
    if hasattr(instance, 'valuecountresult'):
        instance.valuecountresult.delete()


@receiver(pre_save, sender=ReportAggregation, weak=False, dispatch_uid="auto_set_valuecountresult_min_max_dates")
def auto_set_valuecountresult_min_max_dates(sender, instance, **kwargs):
    if instance.composite:
        src_object = instance.composite
    elif instance.predictedlayer:
        src_object = instance.predictedlayer
    else:
        return

    instance.min_date = src_object.min_date
    instance.max_date = src_object.max_date
