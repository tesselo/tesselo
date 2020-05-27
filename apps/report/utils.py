from raster.valuecount import Aggregator

from sentinel.utils import get_raster_tile

VALUECOUNT_ROUNDING_DIGITS = 7


class AggregatorEfficient(Aggregator):
    """
    A patched aggregator function, using the direct S3 tile lookup approach.
    This reduces load on DB dramatically.
    """

    def get_raster_tile(self, layerid, zoom, tilex, tiley):
        return get_raster_tile(layerid, zoom, tilex, tiley)


def populate_vc(vc):
    # Compute range for valuecounts if provided.
    if vc.range_min is not None and vc.range_max is not None:
        hist_range = (vc.range_min, vc.range_max)
    else:
        hist_range = None

    try:
        # Compute aggregate result.
        agg = AggregatorEfficient(
            layer_dict=vc.layer_names,
            formula=vc.formula,
            zoom=vc.zoom,
            geom=vc.aggregationarea.geom,
            acres=vc.units.lower() == 'acres',
            grouping=vc.grouping,
            hist_range=hist_range,
        )
        aggregation_result = agg.value_count()
        vc.stats_min, vc.stats_max, vc.stats_avg, vc.stats_std = agg.statistics()

        # Track cumulative data to be able to generalize stats over
        # multiple aggregation areas.
        vc.stats_cumsum_t0 = agg._stats_t0
        vc.stats_cumsum_t1 = agg._stats_t1
        vc.stats_cumsum_t2 = agg._stats_t2

        # Convert values to string for storage in hstore.
        vc.value = {k: str(round(v, VALUECOUNT_ROUNDING_DIGITS)) for k, v in aggregation_result.items()}

        vc.status = vc.FINISHED
    except:
        vc.status = vc.FAILED

    vc.save()

    return vc
