import numpy

from sentinel import const
from sentinel.clouds.utils import nodata_mask, scale_array


class Clouds(object):

    available_versions = {
        1: 'Average over NDVI and Swir bands.',
        2: 'Purely cloud bands based aggressive cutoff.',
        3: 'Minimum sum of thick cloud and cirrus cloud bands.',
        4: 'Cloud band linear step function approach.',
        5: 'Discretized SceneClass index.',
        6: 'Rank based on SceneClass.',
        7: 'Rank based on SceneClass, flattened.',
    }

    latest_version = 7

    classifier = None

    def __init__(self, ctile):
        if ctile.cloud_classifier:
            self.classifier = ctile.cloud_classifier
        elif ctile.cloud_version is None:
            # Get default latest version.
            ctile.cloud_version = self.latest_version
            ctile.save()
            self.cloud_version = ctile.cloud_version
        else:
            if ctile.cloud_version not in self.available_versions:
                raise NotImplementedError('Requested version {} is not implemented.'.format(ctile.cloud_version))
            self.cloud_version = ctile.cloud_version

    def clouds(self, stack):
        if self.classifier:
            # Convert stack data into input for classifier.
            bands = ['{}.jp2'.format(bnd) for bnd in self.classifier.band_names.split(',')]
            data = numpy.array([stack[bnd].ravel() for bnd in bands]).T
            # Predict cloud probability based on classifier.
            predicted = self.classifier.clf.predict(data).reshape(stack[const.SCL].shape)
            # Add cirrus band values in decimal range as a tie breaker for
            # pixels that do not have a dense.
            return predicted + (numpy.clip(stack[const.BD10], 0, 9999) / 10000)
        else:
            return getattr(self, 'clouds_v{}'.format(self.cloud_version))(stack)

    def clouds_v7(self, stack):
        """
        Scene class pixels ranked by preference. The rank is flattened out so
        that between categories that are similarly desireable, the relative NDVI
        value is decisive.
        """
        SCENE_CLASS_RANK_FLAT = (
            8,   # NO_DATA
            7,   # SATURATED_OR_DEFECTIVE
            5,   # DARK_AREA_PIXELS
            5,   # CLOUD_SHADOWS
            1,   # VEGETATION
            2,   # NOT_VEGETATED
            3,   # WATER
            5,   # UNCLASSIFIED
            6,   # CLOUD_MEDIUM_PROBABILITY
            7,   # CLOUD_HIGH_PROBABILITY
            6,   # THIN_CIRRUS
            4,   # SNOW
        )

        # Use SCL layer to select pixel ranks.
        cloud_probs = numpy.choose(stack[const.SCL], SCENE_CLASS_RANK_FLAT)

        # Ensure nodata pixels have the exclude value.
        cloud_probs[nodata_mask(stack)] = const.EXCLUDE_VALUE

        # Convert cloud probs to float.
        cloud_probs = cloud_probs.astype('float')

        # Compute NDVI, avoiding zero division.
        B4 = stack[const.BD4].astype('float')
        B8 = stack[const.BD8].astype('float')
        ndvi_diff = B8 - B4
        ndvi_sum = B8 + B4
        ndvi_sum[ndvi_sum == 0] = 1
        ndvi = ndvi_diff / ndvi_sum

        # Add inverted and scaled NDVI values to the decimal range of the cloud
        # probs. This ensures that within acceptable pixels, the one with the
        # highest NDVI is selected.
        scaled_ndvi = (1 - ndvi) / 100
        cloud_probs += scaled_ndvi

        return cloud_probs

    def clouds_v6(self, stack):
        """
        All scene class categories are odrered into a rank by preference. The
        lowest rank available is kept as final pixel. For multiple candidates
        with the same rank, the highest NDVI value is kept.
        """

        SCENE_CLASS_RANK = (
            12,  # NO_DATA
            8,   # SATURATED_OR_DEFECTIVE
            5,   # DARK_AREA_PIXELS
            7,   # CLOUD_SHADOWS
            1,   # VEGETATION
            2,   # NOT_VEGETATED
            3,   # WATER
            6,   # UNCLASSIFIED
            10,  # CLOUD_MEDIUM_PROBABILITY
            11,  # CLOUD_HIGH_PROBABILITY
            9,   # THIN_CIRRUS
            4,   # SNOW
        )

        # Use SCL layer to select pixel ranks.
        cloud_probs = numpy.choose(stack[const.SCL], SCENE_CLASS_RANK)

        # Ensure nodata pixels have the exclude value.
        cloud_probs[nodata_mask(stack)] = const.EXCLUDE_VALUE

        # Convert cloud probs to float.
        cloud_probs = cloud_probs.astype('float')

        # Compute NDVI, avoiding zero division.
        B4 = stack[const.BD4].astype('float')
        B8 = stack[const.BD8].astype('float')
        ndvi_diff = B8 - B4
        ndvi_sum = B8 + B4
        ndvi_sum[ndvi_sum == 0] = 1
        ndvi = ndvi_diff / ndvi_sum

        # Add inverted and scaled NDVI values to the decimal range of the cloud
        # probs. This ensures that within acceptable pixels, the one with the
        # highest NDVI is selected.
        scaled_ndvi = (1 - ndvi) / 100
        cloud_probs += scaled_ndvi

        return cloud_probs

    def clouds_v5(stack=None):
        """
        Scene class pixels are divided into three categories. In high and low
        priority, and into a category that is always excluded. Within each
        acceptable cateogry, the higher NDVI value is decisive.
        """
        # Scipy is only installed on workers. So import it when used only.
        from scipy.ndimage import maximum_filter

        # Use SCL layer to select pixel ranks.
        exclude = const.EXCLUDE_VALUE * numpy.isin(stack[const.SCL], const.SCENE_CLASS_EXCLUDE)
        depreoritize = 2 * numpy.isin(stack[const.SCL], const.SCENE_CLASS_DEPREORITIZE)
        keep = 1 * numpy.isin(stack[const.SCL], const.SCENE_CLASS_KEEP)

        # Combine the three layers.
        cloud_probs = keep + depreoritize + exclude

        # Add a maximum filter, to buffer cloudy pixels along the edge by 100m.
        cloud_probs = maximum_filter(cloud_probs, (10, 10))

        # Ensure nodata pixels have the exclude value.
        cloud_probs[nodata_mask(stack)] = const.EXCLUDE_VALUE

        # Convert cloud probs to float.
        cloud_probs = cloud_probs.astype('float')

        # Compute NDVI, avoiding zero division.
        B4 = stack[const.BD4].astype('float')
        B8 = stack[const.BD8].astype('float')
        ndvi_diff = B8 - B4
        ndvi_sum = B8 + B4
        ndvi_sum[ndvi_sum == 0] = 1
        ndvi = ndvi_diff / ndvi_sum

        # Add inverted and scaled NDVI values to the decimal range of the cloud
        # probs. This ensures that within acceptable pixels, the one with the
        # highest NDVI is selected.
        scaled_ndvi = (1 - ndvi) / 100
        cloud_probs += scaled_ndvi

        return cloud_probs

    def clouds_v4(self, stack):
        """
        Piecewise linear functions with spatial max/min filters are used to
        construct a priority index. The cutoff values were determined by
        visual inspection of values in sample images.
        """
        # Scipy is only installed on workers. So import it when used only.
        from scipy.ndimage import maximum_filter, minimum_filter

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
        cloud = thick_cloud + cirrus_cloud

        # Construct final index avoiding shadows and clouds.
        index = cloud + shadow

        # Add nodata mask to maximum to prevent nodata pixel selection.
        # max_val_dtype = numpy.iinfo(stack[const.BD1].dtype).max  # Max value for pixel type.
        # index[nodata_mask(stack)] = max_val_dtype
        index[nodata_mask(stack)] = 4

        return index

    def clouds_v3(self, stack):
        """
        An index is constructed from the cirrus band and one atmospheric
        sensitive infrared band. With a cutoff on band 11.
        """
        from sklearn.preprocessing import minmax_scale
        # Select minimum sum of thick cloud and cirrus cloud bands.
        index = minmax_scale(stack[const.BD1]) + minmax_scale(stack[const.BD10])
        index[(stack[const.BD11] < 900)] = 3
        # Get max value for the datatype.
        # max_val_dtype = numpy.iinfo(stack[const.BD1].dtype).max
        # index[mask] = max_val_dtype
        index[nodata_mask(stack)] = 10

        return index

    def clouds_v2(self, stack):
        """
        Different types of clouds are masked using simple cutoff values per
        band. Dark pixels are determined as well in RGB space. Each type of
        cloud category and shadow pixels are ranked and this rank is used for
        the final decision.
        """
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

    def clouds_v1(self, stack):
        """
        An index is derived using scled NDVI values and the scaled sum of SWIR
        bands. Each dimension has equal weight in the final decision.
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
        cloud_probs[nodata_mask(stack)] = 2

        return cloud_probs
