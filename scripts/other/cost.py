import datetime
import json
import math
import re

from dateutil import parser

from sentinel import const
from sentinel.models import CompositeBuild

# Cost compute data points.
AVERAGE_SIZE_PER_TILE_GB = 619.1 / 7.32e6
COST_PER_PUT =  0.005 / 1000
COST_PER_GET = 0.0004 / 1000
COST_PER_GB_MONTHLY = 0.023
SPOT_DISCOUNT = 0.5
COST_PER_HOUR_SCENES = 0.148 * SPOT_DISCOUNT
COST_PER_HOUR_COMPOSITES = (0.113 / 2) * SPOT_DISCOUNT  # Divided by half, because 2 cpus, 1 prcess per cpu.


def compute_price(compositebuild_id):
    # Get build object.
    build = CompositeBuild.objects.get(pk=compositebuild_id)

    # SCENE INGESTION
    scenes_data = []
    for stile in build.sentineltiles.all():
        # Initiate tracking dict.
        tile_counts = {
            'stile': stile.id,
            'prefix': stile.prefix,
            'tiles_created': 0,
            'band_counts': {},
        }

        # Count number of tiles created.
        for band in stile.sentineltileband_set.all():
            count = band.layer.rastertile_set.count()
            tile_counts['band_counts'][band.band] = count
            tile_counts['tiles_created'] += count

        # Parse timings from log.
        log_times = [dat.group(0) for dat in re.finditer('(?<=\[).+?(?=\])', stile.log)]
        start = parser.parse(log_times[0])
        end = parser.parse(log_times[-1])
        tile_counts['time_elapsed'] = end - start

        # Append to data array.
        scenes_data.append(tile_counts)

    # Compute totals.
    scenes_time_elapsed = datetime.timedelta()
    scenes_tiles_created = 0
    for dat in scenes_data:
        scenes_time_elapsed += dat['time_elapsed']
        scenes_tiles_created += dat['tiles_created']

    # COMPOSITE BUILDING
    composite_data = []
    for ctile in build.compositetiles.all():
        # Compute how many tiles were created based on tile scale.
        tiles_at_max_zoom = (ctile.tilez - const.ZOOM_LEVEL_10M) ** 4
        tiles_created = sum([math.ceil(tiles_at_max_zoom / (2 ** n)) for n in range(const.ZOOM_LEVEL_10M + 1)])
        tile_counts = {
            'ctile': ctile.id,
            'tiles_created': tiles_created,
            'time_elapsed': ctile.end - ctile.start,
        }
        composite_data.append(tile_counts)

    composite_time_elapsed = datetime.timedelta()
    composite_tiles_created = 0
    for dat in composite_data:
        composite_time_elapsed += dat['time_elapsed']
        composite_tiles_created += dat['tiles_created']

    # Add key data to result.
    result = {
        'scenes_time_elapsed_hours': scenes_time_elapsed.total_seconds() / (60 * 60),
        'scenes_tiles_created': scenes_tiles_created,
        'scenes_cost_compute': scenes_time_elapsed.total_seconds() / (60 * 60) * COST_PER_HOUR_SCENES,
        'scenes_cost_storage_create': scenes_tiles_created * COST_PER_PUT,
        'scenes_cost_storage_keep_monthly': scenes_tiles_created * AVERAGE_SIZE_PER_TILE_GB * COST_PER_GB_MONTHLY,
        'composite_time_elapsed_hours': composite_time_elapsed.total_seconds() / (60 * 60),
        'composite_tiles_created': composite_tiles_created,
        'composite_cost_compute': composite_time_elapsed.total_seconds() / (60 * 60) * COST_PER_HOUR_COMPOSITES,
        'composite_cost_storage_create': composite_tiles_created * COST_PER_PUT,
        'composite_cost_storage_touch_scenes': composite_tiles_created * len(const.BAND_CHOICES) * COST_PER_GET,
        'composite_cost_storage_keep_monthly': composite_tiles_created * AVERAGE_SIZE_PER_TILE_GB * COST_PER_GB_MONTHLY,
    }

    # Compute totals.
    result['total_cost_create'] = result['scenes_cost_compute'] + result['scenes_cost_storage_create'] + result['composite_cost_compute'] + result['composite_cost_storage_create'] + result['composite_cost_storage_touch_scenes']
    result['total_montly_cost_keep'] = result['scenes_cost_storage_keep_monthly'] + result['composite_cost_storage_keep_monthly']

    # Print result to console.
    print(json.dumps(result, indent=4))

    # Add detailed data to result.
    result.update({
        'scenes': scenes_data,
        'composite': composite_data,
    })

    return result
