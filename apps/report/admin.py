from django.contrib.gis import admin
from report.models import ReportAggregation, ReportSchedule, ReportScheduleTask
from report.tasks import push_reports


class ReportScheduleAdmin(admin.ModelAdmin):
    actions = ['run_schedule', ]

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
