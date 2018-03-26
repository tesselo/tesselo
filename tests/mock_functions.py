import io
import os

import botocore
import botocore.session
import numpy
from botocore.stub import Stubber
from raster.models import RasterLayer, RasterTile
from raster.tiles.const import WEB_MERCATOR_SRID
from raster.tiles.utils import tile_bounds, tile_index_range, tile_scale

from django.contrib.gis.gdal import GDALRaster
from django.core.files import File
from django.utils import timezone
from sentinel import const
from sentinel.models import SentinelTile, SentinelTileBand, SentinelTileSceneClass


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

    if band == const.SCL:
        max_val = 11
    else:
        max_val = 10000

    # Create a file based raster of the desired scale.
    data = numpy.random.random_integers(0, max_val, size * size).reshape(size, size).astype(numpy.int16)

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


def get_numpy_tile(prefix, tilez, tilex, tiley):
    class FakeTile(object):
        rast = None
    tile = FakeTile()
    data = numpy.random.random_integers(0, 1e4, (256, 256)).astype('uint16')
    tile.rast = GDALRaster({
        'width': 256,
        'height': 256,
        'origin': (11843687, -458452),
        'scale': [10, -10],
        'srid': WEB_MERCATOR_SRID,
        'datatype': 2,
        'bands': [
            {'nodata_value': 0, 'data': data},
        ],
    })
    return tile


def patch_process_l2a(stile_id):
    # Get sentineltile.
    stile = SentinelTile.objects.get(id=stile_id)
    # Fake finished status on sentineltile.
    stile.write('Finished L2A upgrade.', SentinelTile.FINISHED, const.LEVEL_L2A)
    # Ensure sentineltilebands exist.
    for band, desc in const.BAND_CHOICES:
        if not SentinelTileBand.objects.filter(band=band, tile=stile).exists():
            rst = RasterLayer.objects.create(name='Test raster ' + band + ' 1')
            SentinelTileBand.objects.create(band=band, tile=stile, layer=rst)
    # Set bbox for writing fake tiles.
    bbox = [11833687.0, -469452.0, 11859687.0, -441452.0]
    # Create fake gdalraster tiles in sentinel tile bands.
    for band in stile.sentineltileband_set.all():
        # Get band resolution.
        res = const.BAND_RESOLUTIONS[band.band]
        if res == 10:
            zoom = 14
        elif res == 20:
            zoom = 13
        else:
            zoom = 11
        # Compute geotransform for this raster tile.
        idxr = tile_index_range(bbox, zoom, tolerance=1e-3)
        bounds = tile_bounds(idxr[0], idxr[1], zoom)
        # Setup random data.
        data = numpy.random.random_integers(0, 1e4, (256, 256)).astype('uint16')
        # Create raster.
        dest = GDALRaster({
            'width': 256,
            'height': 256,
            'origin': (bounds[0], bounds[1]),
            'scale': [res, -res],
            'srid': WEB_MERCATOR_SRID,
            'datatype': 2,
            'bands': [
                {'nodata_value': 0, 'data': data},
            ],
        })
        # Write raster tile.
        dest = io.BytesIO(dest.vsi_buffer)
        dest = File(dest, name='tile.tif')
        RasterTile.objects.create(
            rasterlayer=band.layer,
            tilex=idxr[0],
            tiley=idxr[1],
            tilez=zoom,
            rast=dest,
        )
    # Ensure scene class exists.
    if not hasattr(stile, 'sentineltilesceneclass'):
        rst = RasterLayer.objects.create(name='Test raster sceneclass')
        SentinelTileSceneClass.objects.create(tile=stile, layer=rst)
    # Compute geotransform for this scene class.
    zoom = 13
    idxr = tile_index_range(bbox, zoom, tolerance=1e-3)
    bounds = tile_bounds(idxr[0], idxr[1], zoom)
    # Setup random data.
    data = numpy.random.random_integers(0, 11, (256, 256)).astype('uint8')
    # Create raster.
    dest = GDALRaster({
        'width': 256,
        'height': 256,
        'origin': (bounds[0], bounds[1]),
        'scale': [res, -res],
        'srid': WEB_MERCATOR_SRID,
        'datatype': 1,
        'bands': [
            {'nodata_value': 0, 'data': data},
        ],
    })
    # Write raster tile.
    dest = io.BytesIO(dest.vsi_buffer)
    dest = File(dest, name='tile.tif')
    RasterTile.objects.create(
        rasterlayer=stile.sentineltilesceneclass.layer,
        tilex=idxr[0],
        tiley=idxr[1],
        tilez=zoom,
        rast=dest,
    )
