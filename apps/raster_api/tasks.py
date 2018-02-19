from raster_aggregation.models import ValueCountResult
from zappa.async import task


@task
def compute_single_value_count_result(valuecount_id):
    """
    Computes value counts for a given input set.
    """
    vc = ValueCountResult.objects.get(id=valuecount_id)
    # If this object was newly created, populate its value count asynchronously.
    if vc.status not in (ValueCountResult.COMPUTING, ValueCountResult.FINISHED):
        vc.populate()
