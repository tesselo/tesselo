from raster_aggregation.models import AggregationLayer

from classify.models import PredictedLayer
from django.contrib.gis import admin
from formulary.models import Formula
from report.models import ReportAggregation, ReportSchedule, ReportScheduleTask
from report.tasks import push_reports
from sentinel.models import Composite


class AggregationLayerInline(admin.TabularInline):
    model = AggregationLayer.reportschedule_set.through
    raw_id_fields = ('aggregationlayer', )
    extra = 0


class PredictedLayerInline(admin.TabularInline):
    model = PredictedLayer.reportschedule_set.through
    extra = 0


class FormulaInline(admin.TabularInline):
    model = Formula.reportschedule_set.through
    extra = 0


class CompositeInline(admin.TabularInline):
    model = Composite.reportschedule_set.through
    extra = 0


class ReportScheduleAdmin(admin.ModelAdmin):
    actions = ['run_schedule', ]
    inlines = (AggregationLayerInline, PredictedLayerInline, FormulaInline, CompositeInline, )
    exclude = ('aggregationlayers', 'predictedlayers', 'formulas', 'composites', )

    def run_schedule(self, request, queryset):
        """
        Run this schedule manually. Will happen on signal basis as well.
        """
        for obj in queryset:
            push_reports('reportschedule', obj.id)
            self.message_user(request, 'Started report building for {}'.format(obj))


class ReportAggregationAdmin(admin.ModelAdmin):
    readonly_fields = (
        'formula', 'aggregationlayer', 'aggregationarea', 'composite',
        'predictedlayer', 'valuecountresult',
    )


class ReportScheduleTaskAdmin(admin.ModelAdmin):
    list_filter = ('status', )


admin.site.register(ReportSchedule, ReportScheduleAdmin)
admin.site.register(ReportScheduleTask, ReportScheduleTaskAdmin)
admin.site.register(ReportAggregation, ReportAggregationAdmin)
