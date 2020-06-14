from raster_aggregation.models import ValueCountResult
from raster_aggregation.tasks import aggregation_layer_parser
from zappa.asynchronous import task


def compute_single_value_count_result(valuecount_id):
    """
    Computes value counts for a given input set.
    """
    vc = ValueCountResult.objects.get(id=valuecount_id)
    # If this object was newly created, populate its value count asynchronously.
    if vc.status not in (ValueCountResult.COMPUTING, ValueCountResult.FINISHED):
        vc.populate()


@task
def compute_single_value_count_result_async(valuecount_id):
    compute_single_value_count_result(valuecount_id)


@task
def aggregation_layer_parser_async(aggregationlayer_id):
    aggregation_layer_parser(aggregationlayer_id)
