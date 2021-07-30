import numpy
from django.test import TestCase

from sentinel.tasks import aggregate_tile, disaggregate_tile


class AggregatorTests(TestCase):

    def test_continuous_aggregator(self):
        tile = numpy.arange(512 * 512).reshape((512, 512)).astype('uint8')
        # Continuous case.
        result = aggregate_tile(tile, target_dtype='uint16')
        self.assertEqual(7, result[0, 3])
        self.assertEqual(result.dtype, numpy.uint16)

    def test_discrete_aggregator(self):
        tile = numpy.arange(512 * 512).reshape((512, 512)).astype('uint8')
        # Discrete case.
        result = aggregate_tile(tile, target_dtype='uint16', discrete=True)
        self.assertEqual(7, result[0, 3])
        self.assertEqual(result.dtype, numpy.uint16)

    def test_disaggregator(self):
        data = numpy.arange(1, 256 * 256 + 1)
        factor = 2

        offsetx = 128
        offsety = 128
        result = disaggregate_tile(data, factor, offsetx, offsety)
        self.assertEqual(result[255, 255], 256 * 256)
        self.assertEqual(result[0, 0], 256 * 128 + 128 + 1)

        offsetx = 128
        offsety = 0
        result = disaggregate_tile(data, factor, offsetx, offsety)
        self.assertEqual(result[0, 0], 128 + 1)
        self.assertEqual(result[255, 255], 256 * 128)

        offsetx = 0
        offsety = 128
        result = disaggregate_tile(data, factor, offsetx, offsety)
        self.assertEqual(result[0, 0], 256 * 128 + 1)
