from unittest.mock import patch

import botocore
import botocore.session
from botocore.stub import Stubber
from raster.models import RasterLayer, RasterTile

from django.test import TestCase, override_settings
from sentinel.models import MGRSTile, SentinelTile, SentinelTileBand
from sentinel.tasks import clear_sentineltile


def client_delete_objects(*args, **kwargs):
    """
    Fake object deletion.
    """
    s3 = botocore.session.get_session().create_client('s3')

    stubber = Stubber(s3)

    stubber.add_response('delete_objects', {})
    stubber.add_response('delete_objects', {})

    stubber.activate()

    return s3


@patch('sentinel.tasks.boto3.session.Session.client', client_delete_objects)
@override_settings(AWS_STORAGE_BUCKET_NAME_MEDIA='test')
class SentinelClearDataTest(TestCase):

    def test_scene_clearing(self):
        mgrs = MGRSTile.objects.create(utm_zone='1', latitude_band='1', grid_square='A')

        stile = SentinelTile.objects.create(
            prefix='test',
            datastrip='test',
            product_name='test',
            mgrstile=mgrs,
            collected='2019-01-01',
            data_coverage_percentage=10,
            cloudy_pixel_percentage=10,
        )
        sbands = [
            SentinelTileBand.objects.create(tile=stile, band='B01.jp2', layer=RasterLayer.objects.create(name='b01')),
            SentinelTileBand.objects.create(tile=stile, band='SCL.jp2', layer=RasterLayer.objects.create(name='scl')),
        ]

        for band in sbands:
            for i in range(10):
                RasterTile.objects.create(
                    rasterlayer=band.layer,
                    tilex=i,
                    tiley=i,
                    tilez=14,
                    rast='abc' + str(i),
                )

        for band in stile.sentineltileband_set.all():
            self.assertTrue(band.layer.rastertile_set.count() > 0)

        clear_sentineltile(stile.id)

        for band in stile.sentineltileband_set.all():
            self.assertEqual(band.layer.rastertile_set.count(), 0)
