from report.models import ReportSchedule


def push_reports(model, pk):
    # Find schedules to push.
    if model == 'reportschedule':
        schedules = ReportSchedule.objects.filter(id=pk)
    elif model == 'composite':
        schedules = ReportSchedule.objects.filter(composite_id=pk)
    elif model == 'predictedlayer':
        schedules = ReportSchedule.objects.filter(predictedlayer_id=pk)
    elif model == 'aggregationlayer':
        schedules = ReportSchedule.objects.filter(aggregationlayer_id=pk)
    elif model == 'formula':
        schedules = ReportSchedule.objects.filter(formula_id=pk)
    else:
        ValueError('Failed finding reports to push.')

    # Push each schedule.
    for sc in schedules:
        sc.populate()
