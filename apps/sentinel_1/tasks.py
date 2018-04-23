import json

import boto3

from django.contrib.gis.gdal import OGRGeometry
from django.contrib.gis.geos import Polygon
from sentinel_1 import const
from sentinel_1.models import Sentinel1Tile


def ingest_s1_tile_from_prefix(tile_prefix, client=None):
    if not client:
        client = boto3.client('s3')

    # Construct TileInfo file key.
    tileinfo_key = tile_prefix + const.TILE_INFO_FILE

    # Get tile info json data.
    tileinfo = client.get_object(Key=tileinfo_key, Bucket=const.BUCKET_NAME, RequestPayer='requester',)
    tileinfo = json.loads(tileinfo.get(const.TILEINFO_BODY_KEY).read().decode())

    if 'footprint' in tileinfo:
        footprint = OGRGeometry(str(tileinfo['footprint'])).geos

        if not isinstance(footprint, Polygon):
            footprint = Polygon(footprint, srid=footprint.srid)

        # Set geom to none if tile data geom is not valid.
        if not footprint.valid:
            footprint = None
    else:
        footprint = None

    # Register tile, log error if creation failed.
    Sentinel1Tile.objects.create(
        product_name=tileinfo['id'],
        prefix=tile_prefix,
        mission_id=tileinfo['missionId'],
        product_type=tileinfo['productType'],
        mode=tileinfo['mode'],
        polarization=tileinfo['polarization'],
        start_time=tileinfo['startTime'],
        stop_time=tileinfo['stopTime'],
        absolute_orbit_number=tileinfo['absoluteOrbitNumber'],
        mission_datatake_id=tileinfo['missionDataTakeId'],
        product_unique_identifier=tileinfo['productUniqueIdentifier'],
        sci_hub_id=tileinfo['sciHubId'],
        footprint=footprint,
        filename_map=tileinfo['filenameMap'],
    )


def process_sentinel_sns_message(event, context):
    """
    Ingest tile data based on notifications from SNS topic
    arn:aws:sns:eu-west-1:214830741341:NewSentinel2Product
    """
    message = json.loads(event['Records'][0]['Sns']['Message'])

    # Get prefix for this tile.
    tile_prefix = message['path']

    # Ensure prefix has trailing slash.
    if not tile_prefix.endswith('/'):
        tile_prefix += '/'

    # Skip this tile if it's already registered.
    if Sentinel1Tile.objects.filter(prefix=tile_prefix).exists():
        return

    ingest_s1_tile_from_prefix(tile_prefix)
