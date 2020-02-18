import datetime

from raster_aggregation.models import AggregationLayer

from jobs import ecs
from report.models import ReportAggregation, ReportSchedule, ReportScheduleTask
from report.utils import populate_vc


def push_reports(model, pk):
    """
    Push report tasks.
    """
    from sentinel.models import Composite
    from formulary.models import Formula
    from classify.models import PredictedLayer

    # Find schedules to push for the targt object.
    if model == 'composite':
        schedules = ReportSchedule.objects.filter(composites__id=pk)
    elif model == 'predictedlayer':
        schedules = ReportSchedule.objects.filter(predictedlayers__id=pk)
    elif model == 'aggregationlayer':
        schedules = ReportSchedule.objects.filter(aggregationlayers__id=pk)
    elif model == 'formula':
        schedules = ReportSchedule.objects.filter(formulas__id=pk)
    elif model == 'reportschedule':
        schedules = ReportSchedule.objects.filter(id=pk)
    else:
        raise ValueError('Failed finding reports to push.')

    # Reduce to active report schedules.
    schedules = schedules.filter(active=True)

    # Retrieve the related models that are affected.
    if model == 'aggregationlayer':
        aggs = [pk]
    else:
        aggs = AggregationLayer.objects.filter(reportschedule__in=schedules).values_list('id', flat=True)

    if model == 'predictedlayer':
        predictedlayers = [pk]
    else:
        predictedlayers = PredictedLayer.objects.filter(reportschedule__in=schedules).values_list('id', flat=True)

    if model == 'composites':
        composites = [pk]
    else:
        composites = Composite.objects.filter(reportschedule__in=schedules).values_list('id', flat=True)

    if model == 'formula':
        formulas = [pk]
    else:
        formulas = Formula.objects.filter(reportschedule__in=schedules).values_list('id', flat=True)

    # Create list of combinations that need updating from the related models.
    combos = []
    for agg in aggs:
        # Ignore composites that are in the future.
        for composite in composites.filter(min_date__lte=datetime.datetime.now().date()):
            for formula in formulas:
                combos.append((agg, composite, formula, None))
        for pred in predictedlayers:
            combos.append((agg, None, None, pred))

    # Push each combination as an async task.
    for combo in combos:
        # Get report schedule task tracker.
        task, created = ReportScheduleTask.objects.get_or_create(
            aggregationlayer_id=combo[0],
            composite_id=combo[1],
            formula_id=combo[2],
            predictedlayer_id=combo[3],
        )
        # Skip if this task is already running.
        if task.status in [ReportScheduleTask.PENDING, ReportScheduleTask.PROCESSING]:
            continue

        # Schedule report task for this combo.
        task.write('Scheduled report task.', ReportScheduleTask.PENDING)
        ecs.populate_report(*combo)


def populate_report(aggregationlayer_id, composite_id, formula_id, predictedlayer_id):
    """
    Run populate script for this report schedule.
    """
    lookup = {
        'aggregationlayer_id': int(aggregationlayer_id)
    }
    # Try converting inputs to integer, if fails, the input was most likely a
    # "None" string. If data was provided, add it as query string for the report
    # aggregation lookup.
    try:
        lookup['composite_id'] = int(composite_id)
    except ValueError:
        pass

    try:
        lookup['formula_id'] = int(formula_id)
    except ValueError:
        pass

    try:
        lookup['predictedlayer_id'] = int(predictedlayer_id)
    except (ValueError, TypeError):
        pass

    # Get report schedule task tracker.
    task, created = ReportScheduleTask.objects.get_or_create(**lookup)

    # Do not run aggregations if they are already in progress.
    if task.status == ReportScheduleTask.PROCESSING:
        return

    # Get aggregation layer.
    aggregationlayer = AggregationLayer.objects.get(id=aggregationlayer_id)

    # Initiate progress log.
    total_jobs = aggregationlayer.aggregationarea_set.all().count()
    task.write('Started aggregation task for {} areas.'.format(total_jobs), ReportScheduleTask.PROCESSING)

    # Loop through all aggregation areas for this layer.
    counter = 0
    for agg in aggregationlayer.aggregationarea_set.all():
        counter += 1
        # Retrieve current aggregation or create a new one.
        try:
            rep = ReportAggregation.objects.get(aggregationarea=agg, **lookup)
        except ReportAggregation.DoesNotExist:
            rep = ReportAggregation(aggregationarea=agg, **lookup)

        # Reset valuecount result object.
        vc = rep.get_valuecount()
        # Update the aggregation values, with minimal DB interactions.
        vc = populate_vc(vc)
        # Store valuecount link.
        rep.valuecountresult = vc
        rep.save()
        # Log progress.
        if counter % 250 == 0:
            task.write('Completed {}/{} aggregations.'.format(counter, total_jobs))

    task.write('Finished aggregation task.', ReportScheduleTask.FINISHED)
