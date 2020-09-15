import numpy
from django.test import TestCase

from sentinel.tasks import aggregate_tile, disaggregate_tile


class AggregatorTests(TestCase):

    def test_continuous_aggregator(self):
        tile = (numpy.random.random_sample((256, 256)) * 100).astype('uint8')
        # Continuous case.
        result = aggregate_tile(tile, target_dtype='uint16')
        self.assertEqual(numpy.mean(numpy.take(tile, [0, 1, 256, 257])).astype('uint16'), result[0, 0])

    def test_discrete_aggregator(self):
        tile = (numpy.random.random_sample((256, 256)) * 100).astype('uint8')
        # Discrete case.
        result = aggregate_tile(tile, target_dtype='uint8', discrete=True)
        self.assertEqual(tile.reshape(256, 256)[0, 6], result[0, 3])

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
