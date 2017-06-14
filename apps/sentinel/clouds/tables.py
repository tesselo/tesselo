from __future__ import unicode_literals

import numpy
from sentinel import const


def clouds(stack):
    """
    Wrapper function to call L2A Scene Class.
    """
    # Get sum of SWIR bands - the brighter the pixel in SWIR, the more
    # likely it is a cloud.
    swir = numpy.clip(stack['B10.jp2'], 0, 1e4) + numpy.clip(stack['B11.jp2'], 0, 1e4) + numpy.clip(stack['B12.jp2'], 0, 1e4)
    # Normalize to range [0, 1].
    swir = swir / 3e4
    # Compute inverted NDVI - less green is highter cloud probability.
    # Avoiding zero division.
    ndvi_sum = stack['B08.jp2'] + stack['B04.jp2']
    ndvi_sum[ndvi_sum == 0] = 1
    ndvi_diff = stack['B04.jp2'].astype('float') - stack['B08.jp2'].astype('float')
    ndvi = ndvi_diff / ndvi_sum
    # Normalize to [0, 1].
    ndvi = (ndvi + 1) / 2
    # Define cloud probs as the average of the two values.
    cloud_probs = (swir + ndvi) / 2

    # Set nodata pixels to higher than highest cloud probability, so
    # that NA values are only selected if none of the scenes had any
    # data available.
    cloud_probs[stack[const.BD2] == const.SENTINEL_NODATA_VALUE] = 2

    return cloud_probs