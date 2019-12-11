import datetime

from raster_aggregation.models import AggregationArea, AggregationLayer, ValueCountResult

from classify.models import PredictedLayer
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from sentinel.models import Composite


class ReportSchedule(models.Model):
    """
    Schedule automatic aggregation over an aggregationlayer using every
    combination of the formulas, composites, and predicted layers specified.
    """
    aggregationlayers = models.ManyToManyField(AggregationLayer)
    formulas = models.ManyToManyField('formulary.Formula')
    composites = models.ManyToManyField(Composite)
    predictedlayers = models.ManyToManyField(PredictedLayer)
    active = models.BooleanField(default=False)

    def __str__(self):
        return '{} | Aggs {}, Comps {}, Forms {}, Preds {}'.format(
            self.id,
            self.aggregationlayers.count(),
            self.composites.count(),
            self.formulas.count(),
            self.predictedlayers.count(),
        )


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

    formula = models.ForeignKey('formulary.Formula', on_delete=models.CASCADE, blank=True, null=True, help_text='Leave empty for predicted layers.')
    aggregationlayer = models.ForeignKey(AggregationLayer, on_delete=models.CASCADE)
    aggregationarea = models.ForeignKey(AggregationArea, on_delete=models.CASCADE)

    composite = models.ForeignKey(Composite, on_delete=models.CASCADE, blank=True, null=True)
    predictedlayer = models.ForeignKey(PredictedLayer, on_delete=models.CASCADE, blank=True, null=True)

    valuecountresult = models.OneToOneField(ValueCountResult, on_delete=models.CASCADE, blank=True)

    def __str__(self):
        return '{} | Agg {}, Comp {}, Form {}, Pred {}'.format(
            self.id,
            self.aggregationlayer,
            self.composite,
            self.formula,
            self.predictedlayer,
        )

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


@receiver(post_delete, sender=ReportAggregation, weak=False, dispatch_uid="remove_valuecount_before_delete")
def check_change_on_formula(sender, instance, **kwargs):
    if hasattr(instance, 'valuecountresult'):
        instance.valuecountresult.delete()
