from __future__ import unicode_literals

import numpy

from sentinel import const

# from scipy.ndimage import maximum_filter, minimum_filter
# from sklearn.preprocessing import minmax_scale



def nodata_mask(stack):
    """
    Compute mask that indicates nodata pixels over all bands. This mask can be
    used to avoid selecting nodata pixels in composites.
    """
    return numpy.any([
        stack[const.BD2] == const.SENTINEL_NODATA_VALUE,  # 10m
        stack[const.BD12] == const.SENTINEL_NODATA_VALUE,  # 20m
        stack[const.BD1] == const.SENTINEL_NODATA_VALUE,  # 60m
    ], axis=0)


def scale_array(arr, vmin, vmax):
    arr = numpy.clip(arr, vmin, vmax)
    return (arr - vmin) / (vmax - vmin)


def clouds_v3(stack):
    # Select minimum sum of thick cloud and cirrus cloud bands.
    index = minmax_scale(stack[const.BD1]) + minmax_scale(stack[const.BD10])
    index[(stack[const.BD11] < 900)] = 3
    # Get max value for the datatype.
    # max_val_dtype = numpy.iinfo(stack[const.BD1].dtype).max
    # index[mask] = max_val_dtype
    index[nodata_mask(stack)] = 10

    return index


def clouds(stack):
    # Maximum and minimum filters will ensure that the cloud edges are
    # recognized as such. Between cloud and shadow, the values have normal
    # range and would be confused with good pixels.
    FILTER_SIZE_20 = (15, 15)
    FILTER_SIZE_60 = (20, 20)

    # Select cloud shadows.
    SHADOW_LOW = 800  # Certainly shadow.
    SHADOW_HIGH = 2000  # Certainly not shadow.
    shadow = 1 - scale_array(
        minimum_filter(stack[const.BD11], size=FILTER_SIZE_20),
        SHADOW_LOW,
        SHADOW_HIGH
    )

    # Select thick cloud band.
    THICK_CLOUD_LOW = 1600  # Certainly not cloud.
    THICK_CLOUD_HIGH = 3000  # Certainly cloud.
    thick_cloud = scale_array(
        maximum_filter(stack[const.BD1], FILTER_SIZE_60),
        THICK_CLOUD_LOW,
        THICK_CLOUD_HIGH,
    )

    # Select cirrus cloud band.
    CIRRUS_LOW = 20  # Certainly not cirrus.
    CIRRUS_HIGH = 100  # Certainly cirrus.
    cirrus_cloud = scale_array(
        maximum_filter(stack[const.BD10], FILTER_SIZE_60),
        CIRRUS_LOW,
        CIRRUS_HIGH,
    )

    # Construct cloud index with equal weights for cirrus and thick.
    # cloud = thick_cloud
    cloud = thick_cloud + cirrus_cloud
    # cloud = minmax_scale(thick_cloud + cirrus_cloud)

    # Construct final index avoiding shadows and clouds.
    index = cloud + shadow

    # Add nodata mask to maximum to prevent nodata pixel selection.
    # max_val_dtype = numpy.iinfo(stack[const.BD1].dtype).max  # Max value for pixel type.
    # index[nodata_mask(stack)] = max_val_dtype
    index[nodata_mask(stack)] = 4

    return index


def clouds_v2(stack):
    # Aggressive cutoff for thick clouds.
    thick = stack[const.BD1] > 2000
    # Aggressive cutoff for cirrus clouds.
    cirrus = stack[const.BD10] > 60
    # Bright edge pixels.
    edge = (stack[const.BD2] + stack[const.BD3] + stack[const.BD4]) > (1500 * 3)
    # Dark pixel index. Once clouds are masked, use the brightest remaining
    # pixel to avoid shadows.
    dark = 1 - numpy.clip(stack[const.BD2] + stack[const.BD3] + stack[const.BD4], 1, 3e4).astype('float') / 3e4
    # The cloud index is 5 for nodata, 4 for thick clouds, 3 for cirrus,
    # 2 for bright bixels and [0, 1] for the dark pixel index.
    dark[nodata_mask(stack)] = 5
    dark[thick] = 4
    dark[cirrus] = 3
    dark[edge] = 2

    return dark


def clouds_v1(stack):
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
    cloud_probs[nodata_mask(stack)] = 2

    return cloud_probs
