from raster_aggregation.models import AggregationArea, AggregationLayer, ValueCountResult

from classify.models import PredictedLayer
from django.db import models
from formulary.models import Formula
from report.utils import get_report_obj_str
from sentinel.models import Composite


class ReportSchedule(models.Model):
    """
    Schedule automatic aggregation over an aggregationlayer using a formula and
    a composite, or classes from a predictedlayer.
    """
    aggregationlayer = models.ForeignKey(AggregationLayer, on_delete=models.CASCADE)

    formula = models.ForeignKey(Formula, on_delete=models.CASCADE, blank=True, null=True, help_text='Leave empty for predicted layers.')
    composite = models.ForeignKey(Composite, on_delete=models.CASCADE, blank=True, null=True)

    predictedlayer = models.ForeignKey(PredictedLayer, on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        return 'RSC {} | '.format(self.id) + get_report_obj_str(self)

    def populate(self):
        """
        Loop through aggregation areas for this schedule and run the
        corresponding aggregations.
        """
        for agg in self.aggregationlayer.aggregationarea_set.all():
            # Retrieve current aggregation or create a new one.
            rep, created = ReportAggregation.objects.get_or_create(
                aggregationlayer_id=agg.aggregationlayer_id,
                aggregationarea=agg,
                formula_id=self.formula_id,
                composite_id=self.composite_id,
                predictedlayer_id=self.predictedlayer_id,
            )
            if not created:
                rep.reset()
            # Update the aggregation values.
            rep.valuecountresult.populate()


class ReportAggregation(models.Model):
    """
    Aggregate Sentinel-2 data by formula and aggregation area.
    """

    ZOOM = 14

    formula = models.ForeignKey(Formula, on_delete=models.CASCADE, blank=True, null=True, help_text='Leave empty for predicted layers.')
    aggregationlayer = models.ForeignKey(AggregationLayer, on_delete=models.CASCADE)
    aggregationarea = models.ForeignKey(AggregationArea, on_delete=models.CASCADE)

    composite = models.ForeignKey(Composite, on_delete=models.CASCADE, blank=True, null=True)
    predictedlayer = models.ForeignKey(PredictedLayer, on_delete=models.CASCADE, blank=True, null=True)

    valuecountresult = models.OneToOneField(ValueCountResult, on_delete=models.CASCADE, blank=True)

    def __str__(self):
        return 'RA {} | '.format(self.id) + get_report_obj_str(self)

    def reset(self):
        # Get data for valuecount result update.
        if self.composite:
            formula = self.formula.formula
            layer_names = {
                key.replace('.jp2', '').replace('0', ''): val for key, val in self.composite.rasterlayer_lookup.items()
            }
            # Only keep bands that are present in formula.
            layer_names = {key: val for key, val in layer_names.items() if key in formula}
        elif self.predictedlayer_id:
            # Simple formula for predictedlayers.
            formula = 'x'
            layer_names = {'x': self.predictedlayer.rasterlayer_id}
        else:
            raise ValueError('Specify Composite or PredictedLayer.')

        if self.valuecountresult_id:
            # Update current valuecountresult.
            self.valuecountresult.layer_names=layer_names
            self.valuecountresult.formula=formula
            self.valuecountresult.zoom=self.ZOOM
            self.valuecountresult.aggregationarea=self.aggregationarea
            self.valuecountresult.units='acres'
            self.valuecountresult.grouping='discrete' if self.predictedlayer_id else 'continuous'
            self.valuecountresult.status = ValueCountResult.SCHEDULED
            self.valuecountresult.save()
        else:
            # Create new valuecountresult.
            self.valuecountresult, created = ValueCountResult.objects.get_or_create(
                layer_names=layer_names,
                formula=formula,
                zoom=self.ZOOM,
                aggregationarea=self.aggregationarea,
                units='acres',
                grouping='discrete' if self.predictedlayer_id else 'continuous',
            )

    def save(self, *args, **kwargs):
        if not self.valuecountresult_id:
            self.reset()
        super(ReportAggregation, self).save(*args, **kwargs)
