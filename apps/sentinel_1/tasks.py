import datetime
import glob
import gzip
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import traceback

import boto3
import rasterio
from raster.models import RasterLayer
from raster.tiles.const import WEB_MERCATOR_SRID
from rasterio.warp import Resampling, calculate_default_transform, reproject

from django.contrib.gis.gdal import OGRGeometry
from django.contrib.gis.geos import MultiPolygon
from sentinel.models import CompositeBuild
from sentinel.tasks import composite_build_callback
from sentinel.utils import locally_parse_raster
from sentinel_1 import const
from sentinel_1.models import Sentinel1Tile, Sentinel1TileBand


def parse_s3_sentinel_1_inventory():
    """
    Full Sentinel-1 inventory synchronization.

    aws s3 ls s3://sentinel-inventory/sentinel-s1-l1c/sentinel-s1-l1c-inventory/
    """
    print('Starting inventory sync.')
    client = boto3.client('s3')
    today = datetime.datetime.now().date() - datetime.timedelta(days=1)
    # Get latest inventory manifest (created yesterday).
    manifest = client.get_object(
        Key='sentinel-s1-l1c/sentinel-s1-l1c-inventory/{}T04-00Z/manifest.json'.format(today),
        Bucket=const.INVENTORY_BUCKET_NAME,
    )
    manifest = json.loads(manifest.get(const.TILEINFO_BODY_KEY).read().decode())
    # Loop through inventory files and ingest listed Sentinel-1 scenes.
    for dat in manifest['files']:
        print('Working on file', dat['key'])
        with tempfile.NamedTemporaryFile(suffix='.csv.gz') as csvgz:
            prefixes = set()
            client.download_file(
                Key=dat['key'],
                Bucket=const.INVENTORY_BUCKET_NAME,
                Filename=csvgz.name,
            )
            with gzip.open(csvgz.name, 'rb') as fl:
                for line in fl:
                    # Add prefix to unique list.
                    prefixes.add('/'.join(str(line).replace('"', '').split(',')[1].split('/')[:7]) + '/')
            print('Found {} unique prefixes.'.format(len(prefixes)))
            # Setup s1tiles from unique prefix list.
            batch = []
            counter = 0
            for prefix in prefixes:
                new_tile = ingest_s1_tile_from_prefix(prefix, client, commit=False)
                if not new_tile:
                    continue
                batch.append(new_tile)
                counter += 1
                if counter % 500 == 0:
                    print('Created {} S1 Tiles'.format(counter))
                    Sentinel1Tile.objects.bulk_create(batch)
                    batch = []

            if len(batch):
                Sentinel1Tile.objects.bulk_create(batch)


def ingest_s1_tile_from_prefix(tile_prefix, client=None, commit=True):
    """
    Ingest a Sentinel 1 tile from a prefix. Download metadata for the scene and
    create Sentinel1Tile object containing the data.
    """
    # Ignore this if the tile already exists.
    if Sentinel1Tile.objects.filter(prefix=tile_prefix).exists():
        return
    # Instantiate boto3 client.
    if not client:
        client = boto3.client('s3')

    # Construct TileInfo file key.
    tileinfo_key = tile_prefix + const.TILE_INFO_FILE

    # Get tile info json data.
    tileinfo = client.get_object(
        Key=tileinfo_key,
        Bucket=const.BUCKET_NAME,
        RequestPayer='requester',
    )
    tileinfo = json.loads(tileinfo.get(const.TILEINFO_BODY_KEY).read().decode())

    if 'footprint' in tileinfo:
        footprint = OGRGeometry(str(tileinfo['footprint'])).geos
        if not isinstance(footprint, MultiPolygon):
            # Attempt conversion.
            footprint = MultiPolygon(footprint, srid=footprint.srid)
        # Set geom to none if tile data geom is not valid.
        if not footprint.valid:
            footprint = None
    else:
        footprint = None

    # Register tile, log error if creation failed.
    stile = Sentinel1Tile(
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

    if commit:
        stile.save()

    return stile


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


def snap_terrain_correction(sentinel1tile_id):
    """
    Apply terrain correction graph to sentinel tile.

    See also https://github.com/DHI-GRAS/docker-esa-snap

    Shell run example:

    wd=/s1docker
    input=/data/subset_0_of_S1A_IW_GRDH_1SDV_20170725T063423_20170725T063448_017624_01D7E9_94A3.dim
    output=/data/subset_0_of_S1A_IW_GRDH_1SDV_20170725T063423_20170725T063448_017624_01D7E9_94A3_Orb_NR_Cal_Spk_TC_dB.dim
    docker run --rm -it\
     -v $wd:/data\
     -v /path/to/repo/tesselo/apps/sentinel_1/graphs/snap_terrain_correction.xml:/snap_terrain_correction.xml\
     tesselo-snap bash\
     gpt /snap_terrain_correction.xml \
      -Pinput=$input\
      -Poutput=$output

    Exmample files for testing:

    aws s3 ls s3://sentinel-inventory/sentinel-s1-l1c/sentinel-s1-l1c-inventory/2019-12-04T04-00Z/
    aws s3 sync --request-payer requester s3://sentinel-s1-l1c/GRD/2018/8/12/EW/DH/S1A_EW_GRDH_1SDH_20180812T104348_20180812T104451_023212_0285C2_F7F4 ~/Desktop/s1dwn
    aws s3 ls s3://sentinel-s1-l1c/GRD/2018/8/12/EW/DH/S1A_EW_GRDH_1SDH_20180812T104348_20180812T104451_023212_0285C2_F7F4
    """
    # Get tile object.
    tile = Sentinel1Tile.objects.get(id=sentinel1tile_id)
    tile.write('Started processing tile with Batch Job ID "{}".'.format(os.environ.get('AWS_BATCH_JOB_ID', 'unknown')), Sentinel1Tile.PROCESSING)

    # Download data.
    tile.write('Downloading data.')
    gpt_input_path = os.path.join(const.GPT_WORKDIR, '{}.SAFE'.format(tile.product_name))
    cmd_s3download = 'aws s3 sync --request-payer=requester s3://{}/{} {}'.format(
        const.BUCKET_NAME,
        tile.prefix,
        gpt_input_path,
    )
    subprocess.run(cmd_s3download, shell=True, check=True)

    # Apply graph.
    tile.write('Applying terrain correction graph.')
    gpt_output_path = os.path.join(const.GPT_WORKDIR, '{}_gpt_out.dim'.format(tile.product_name))
    cmd_gpt = const.GPT_TERRAIN_CORRECTION_CMD_TEMPLATE.format(
        input=gpt_input_path,
        output=gpt_output_path,
    )
    subprocess.run(cmd_gpt, shell=True, check=True)

    # Remove original product to save disk space.
    shutil.rmtree(gpt_input_path)

    # Ingest the resulting rasters as tiles.
    gpt_output_file_data_path = os.path.join(const.GPT_WORKDIR, '{}_gpt_out.data'.format(tile.product_name))
    for output_band_path in glob.glob(os.path.join(gpt_output_file_data_path, '*.img')):
        for band_key, name in const.BAND_CHOICES:
            # Continue if this band choice is not present.
            if band_key not in os.path.basename(output_band_path):
                continue
            tile.write('Ingesting band {}.'.format(band_key))
            # Get tile band object.
            band = Sentinel1TileBand.objects.filter(
                tile=tile,
                band=band_key,
            ).first()
            # Create new raster layer and register it as sentinel band.
            if not band:
                rasterlayer = RasterLayer.objects.create(
                    name=tile.prefix + band_key,
                    datatype=RasterLayer.CONTINUOUS,
                    nodata=const.SENTINEL_1_NODATA_VALUE,
                    max_zoom=const.SENTINEL_1_ZOOM,
                    build_pyramid=True,
                    store_reprojected=False,
                )

                # Make Sentinel-1 bands available to all users.
                rasterlayer.publicrasterlayer.public = True
                rasterlayer.publicrasterlayer.save()

                # Register raster layer as Sentinel-1 tile band.
                band = Sentinel1TileBand.objects.create(
                    tile=tile,
                    band=band_key,
                    layer=rasterlayer,
                )
            # Create tempdir for parsing.
            tmpdir = os.path.join(const.GPT_WORKDIR, 'tmp{}'.format(band.id))
            pathlib.Path(tmpdir).mkdir(parents=True, exist_ok=True)
            # Reproject raster into new TIFF file in tmp folder. Use rasterio
            # because of the exotic file type that is not handled well by
            # GDALRaster.
            tile.write('Reprojecting band {}.'.format(band_key))
            dst_crs = 'EPSG:{}'.format(WEB_MERCATOR_SRID)
            with rasterio.open(output_band_path) as src:
                transform, width, height = calculate_default_transform(
                    src.crs,
                    dst_crs,
                    src.width,
                    src.height,
                    *src.bounds,
                )
                kwargs = src.meta.copy()
                kwargs.update({
                    'crs': dst_crs,
                    'transform': transform,
                    'width': width,
                    'height': height,
                    'driver': 'GTiff',
                })
                output_band_path_parser = os.path.join(tmpdir, '{}.tif'.format(band_key))
                with rasterio.open(output_band_path_parser, 'w', **kwargs) as dst:
                    for i in range(1, src.count + 1):
                        reproject(
                            source=rasterio.band(src, i),
                            destination=rasterio.band(dst, i),
                            src_transform=src.transform,
                            src_crs=src.crs,
                            dst_transform=transform,
                            dst_crs=dst_crs,
                            resampling=Resampling.cubic,
                        )

            # Ingest this band.
            tile.write('Parsing band {}.'.format(band_key))
            try:
                locally_parse_raster(os.path.dirname(output_band_path_parser), band.layer.id, output_band_path_parser, const.SENTINEL_1_ZOOM)
            except:
                tile.write('Failed processing band {}. {}'.format(band_key, traceback.format_exc()), Sentinel1Tile.FAILED)
                raise

    tile.write('Finished processing band {}'.format(band_key), Sentinel1Tile.FINISHED)

    # Run callbacks to continue build chain.
    for cbuild in tile.compositebuild_set.filter(status=CompositeBuild.INGESTING_SCENES):
        composite_build_callback(cbuild.id)
