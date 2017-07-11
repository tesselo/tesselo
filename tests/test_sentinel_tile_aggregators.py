from __future__ import unicode_literals

import numpy

from django.test import TestCase
from sentinel.tasks import disaggregate_tile


class AggregatorTests(TestCase):

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
