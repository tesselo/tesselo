from report.models import ReportSchedule
from sentinel import ecs


def push_reports(model, pk):
    """
    Push report tasks.
    """
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

    # Push each schedule as async task.
    for sc in schedules:
        sc.write('Scheduling roport.', ReportSchedule.PENDING)
        ecs.populate_report(sc.id)


def populate_report(pk):
    """
    Run populate script for this report schedule.
    """
    sc = ReportSchedule.objects.get(id=pk)
    sc.populate()
