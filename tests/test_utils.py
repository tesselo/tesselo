import datetime

from django.test import TestCase

from sentinel.clouds.utils import sun


class UtilsTests(TestCase):

    def test_sun(self):
        date = datetime.datetime(1471, 5, 21)
        lat = 49.45386
        lon = 11.07727
        expected = (-0.3481839895248413, 0.2252657562494278)
        self.assertEqual(
            sun(date, lat, lon),
            expected,
        )
