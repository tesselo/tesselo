from __future__ import unicode_literals

import io
import os

import botocore
import botocore.session
import numpy
from botocore.stub import Stubber
from raster.tiles.const import WEB_MERCATOR_SRID
from raster.tiles.utils import tile_scale

from django.contrib.gis.gdal import GDALRaster
from django.utils import timezone
from sentinel import const


def iterator_search(self, searchstring):
    return [
        "tiles/10/S/DG/2015/12/7/0/tileInfo.json",
        "tiles/48/M/XA/2016/5/20/0/tileInfo.json",
        "tiles/48/M/XA/2015/5/20/0/tileInfo.json",
        "tiles/1/C/CV/2015/12/21/0/tileInfo.json",
    ]


def client_get_object(*args, **kwargs):
    s3 = botocore.session.get_session().create_client('s3')
    stubber = Stubber(s3)

    response1 = {
        "AcceptRanges": "bytes",
        "LastModified": timezone.datetime(2016, 3, 30, 3, 10, 13),
        "Metadata": {},
        "ResponseMetadata": {
            "HTTPStatusCode": 200,
            "RequestId": "76A1",
            "HostId": "RB9OvDeI"
        },
        'Body': io.FileIO(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/tileInfo1.json')),
    }
    expected_params = {
        'Key': "tiles/10/S/DG/2015/12/7/0/tileInfo.json",
        'Bucket': const.BUCKET_NAME,
    }
    stubber.add_response('get_object', response1, expected_params)

    response2 = {
        "AcceptRanges": "bytes",
        "LastModified": timezone.datetime(2016, 3, 30, 3, 10, 13),
        "Metadata": {},
        "ResponseMetadata": {
            "HTTPStatusCode": 200,
            "RequestId": "76A1",
            "HostId": "RB9OvDeI"
        },
        'Body': io.FileIO(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/tileInfo2.json')),
    }
    expected_params = {
        'Key': "tiles/48/M/XA/2016/5/20/0/tileInfo.json",
        'Bucket': const.BUCKET_NAME,
    }
    stubber.add_response('get_object', response2, expected_params)

    response2A = {
        "AcceptRanges": "bytes",
        "LastModified": timezone.datetime(2015, 3, 30, 3, 10, 13),
        "Metadata": {},
        "ResponseMetadata": {
            "HTTPStatusCode": 200,
            "RequestId": "76A1",
            "HostId": "RB9OvDeI"
        },
        'Body': io.FileIO(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/tileInfo2A.json')),
    }
    expected_params = {
        'Key': "tiles/48/M/XA/2015/5/20/0/tileInfo.json",
        'Bucket': const.BUCKET_NAME,
    }
    stubber.add_response('get_object', response2A, expected_params)

    response3 = {
        "AcceptRanges": "bytes",
        "LastModified": timezone.datetime(2015, 3, 30, 3, 10, 13),
        "Metadata": {},
        "ResponseMetadata": {
            "HTTPStatusCode": 200,
            "RequestId": "76A1",
            "HostId": "RB9OvDeI"
        },
        'Body': io.FileIO(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data/tileInfo3.json')),
    }
    expected_params = {
        'Key': "tiles/1/C/CV/2015/12/21/0/tileInfo.json",
        'Bucket': const.BUCKET_NAME,
    }
    stubber.add_response('get_object', response3, expected_params)

    stubber.activate()
    return s3


def point_to_test_file(source_url, filepath):
    """
    Mock a sentinel granule file download.
    """
    # Select the raster size and scale based on the band resolution.
    band = source_url.split('/')[-1]
    gensize = 30

    if band in const.BANDS_60M:
        size = gensize
        scale = tile_scale(const.ZOOM_LEVEL_60M) + 1
    elif band in const.BANDS_20M:
        size = gensize * 4
        scale = tile_scale(const.ZOOM_LEVEL_20M) + 1
    elif band in const.BANDS_10M:
        size = gensize * 8
        scale = tile_scale(const.ZOOM_LEVEL_10M) + 1

    # Create a file based raster of the desired scale.
    data = numpy.random.random_integers(0, 10000, size * size).reshape(size, size).astype(numpy.int16)

    GDALRaster({
        'name': filepath,
        'driver': 'tif',
        'width': size,
        'height': size,
        'origin': (11843687, -458452),
        'scale': [scale, -scale],
        'srid': WEB_MERCATOR_SRID,
        'datatype': 2,
        'bands': [
            {'nodata_value': 0, 'data': data},
        ],
    })
