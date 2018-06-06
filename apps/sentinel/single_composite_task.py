import argparse
import glob
import json
import os
import shutil
import subprocess
import sys

import boto3
import numpy
from dateutil import parser, rrule
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import closest_zoomlevel, tile_bounds, tile_index_range, tile_scale
from scipy.ndimage import maximum_filter

from django.conf import settings
from django.contrib.gis.gdal import GDALRaster, OGRGeometry
from sentinel import const

# Fake django environment.
settings.configure()

PRODUCT_DOWNLOAD_CMD_TMPL = 'java -jar /ProductDownload/ProductDownload.jar --sensor S2 --aws --out /products/ --store AWS --limit 1 --tiles {mgrs_code} --start {start} --end {end}'
COMPOSITE_ZOOM = 8
COMPOSITE_SCALE = tile_scale(COMPOSITE_ZOOM)
COMPOSITE_SCAN_SIZE = 183
COMPOSITE_SCAN_COUNT = 30
COMPOSITE_BUCKET = 'composite-single-task'
COMPOSITE_PATH = 'composite'
SCENE_PATH = 'products'
TMS_PATH = 'tms'
SCL_DTYPE = 'uint8'


def tiles_from_to(mgrs_code, start, end):
    """
    List all prefixes from within a time interval.
    """
    s3 = boto3.resource('s3')

    for date in rrule.rrule(rrule.DAILY, dtstart=start, until=end):
        prefix = 'tiles/{utm}/{lat}/{sq}/{yr}/{mo}/{da}/0/'.format(
            utm=mgrs_code[:-3],
            lat=mgrs_code[-3],
            sq=mgrs_code[-2:],
            yr=date.year,
            mo=date.month,
            da=date.day,
        )
        obj = s3.Object('sentinel-s2-l2a', '{prefix}tileInfo.json'.format(prefix=prefix))
        try:
            info = obj.get(RequestPayer='requester')
        except s3.meta.client.exceptions.NoSuchKey:
            obj = s3.Object('sentinel-s2-l1c', '{prefix}tileInfo.json'.format(prefix=prefix))
            try:
                info = obj.get()
            except s3.meta.client.exceptions.NoSuchKey:
                continue
            else:
                level = const.LEVEL_L1C
        else:
            level = const.LEVEL_L2A

        info = info['Body'].read()
        info = json.loads(info.decode())
        yield level, info


def get_data(mgrs_code, start, end, workdir):
    start = parser.parse(start).date()
    end = parser.parse(end).date()
    for level, info in tiles_from_to(mgrs_code, start, end):
        if level == const.LEVEL_L1C:
            pass
        else:
            download_l2a(info, workdir)


def download_l2a(info, workdir):
    print('Downloading L2A data for {}'.format(info['path']))

    # Prepare data dirs.
    tile_dir = info['path'].replace('/', '-')
    try:
        os.makedirs(os.path.join(os.path.join(workdir, SCENE_PATH), tile_dir))
    except OSError:
        pass

    # Download each band and scene class.
    layers = {const.SCL: 20}
    layers.update(const.BAND_RESOLUTIONS)
    for band, resolution in layers.items():
        # Band 10 is not kept in L2A as it does not contain surface
        # information (its fully absorbed in atmosphere, any reflectance
        # is due to atmospheric scattering).
        if band == const.BD10:
            bucket = 'sentinel-s2-l1c'
            prefix = '{prefix}/{band}'.format(
                prefix=info['path'],
                band=band,
            )
        else:
            bucket = 'sentinel-s2-l2a'
            prefix = '{prefix}/R{resolution}m/{band}'.format(
                prefix=info['path'],
                resolution=resolution,
                band=band,
            )
        dest = os.path.join(os.path.join(workdir, SCENE_PATH), tile_dir, band)

        print('Downloading file s3://' + bucket + '/' + prefix)

        s3 = boto3.resource('s3')
        s3.Object(bucket, prefix).download_file(dest, ExtraArgs={'RequestPayer': 'requester'})

        # L2A data in sentinel-s2-l2a bucket does not have an srid and wrong
        # geotransform params. So move data to tif with correct specs.
        original_data = GDALRaster(dest).bands[0].data()
        original_datatype = GDALRaster(dest).bands[0].datatype()
        original_origin = info['tileGeometry']['coordinates'][0][0]

        # Overwrite original file, to keep naming convention (this writes tif
        # files with jp2 extension).
        GDALRaster({
            'name': dest,
            'srid': int(info['tileGeometry']['crs']['properties']['name'].split(':')[-1]),
            'driver': 'tif',
            'datatype': original_datatype,
            'origin': original_origin,
            'width': original_data.shape[1],
            'height': original_data.shape[0],
            'scale': [resolution, -resolution],
            'bands': [{'nodata_value': const.SENTINEL_NODATA_VALUE, 'data': original_data}],
        })

    print('Finished L2A product download for {}'.format(info['path']))


def compute_cloud_probs(tile_list, offset, size):
    result = []
    for tile in tile_list:
        scl_data = GDALRaster(os.path.join(tile, const.SCL)).bands[0].data(offset=offset, size=size)

        # Use SCL layer to select pixel ranks.
        nodata = 4 * numpy.isin(scl_data, const.SENTINEL_NODATA_VALUE)
        exclude = 3 * numpy.isin(scl_data, const.SCENE_CLASS_EXCLUDE)
        depreoritize = 2 * numpy.isin(scl_data, const.SCENE_CLASS_DEPREORITIZE)
        keep = 1 * numpy.isin(scl_data, const.SCENE_CLASS_KEEP)

        # Combine the three layers.
        cloud_probs = keep + depreoritize + exclude + nodata

        # Add a maximum filter, to buffer cloudy pixels along the edge by 100m.
        cloud_probs = maximum_filter(cloud_probs, (5, 5))

        result.append(cloud_probs)

    return result


def write_composite(output_dir, band, tile_list, choice, idx1, idx2, offset, size):
    target = GDALRaster(os.path.join(output_dir, band), write=True)
    stack = numpy.array([GDALRaster(os.path.join(tile, band)).bands[0].data(offset=offset, size=size) for tile in tile_list])
    composite_data = stack[choice, idx1, idx2]
    target.bands[0].data(composite_data, offset=offset, size=size)


def create_composite(workdir):
    # Get scene list.
    tile_list = glob.glob(os.path.join(os.path.join(workdir, SCENE_PATH), '*'))

    # Copy first stack to create target rasters.
    shutil.rmtree(os.path.join(workdir, COMPOSITE_PATH), ignore_errors=True)
    shutil.copytree(tile_list[0], os.path.join(workdir, COMPOSITE_PATH))

    # Write composites in parts.
    for i in range(COMPOSITE_SCAN_COUNT):
        for j in range(COMPOSITE_SCAN_COUNT):
            offset_20m = (i * COMPOSITE_SCAN_SIZE, j * COMPOSITE_SCAN_SIZE)
            size_20m = (COMPOSITE_SCAN_SIZE, COMPOSITE_SCAN_SIZE)

            if (i * COMPOSITE_SCAN_COUNT + j) % 50 == 0:
                print('Processed {}/{} tiles'.format(i * COMPOSITE_SCAN_COUNT + j, COMPOSITE_SCAN_COUNT ** 2))

            # Compute rank for each scene class layer.
            cloud_probs = compute_cloud_probs(tile_list, offset_20m, size_20m)

            # Create choice layer from scene class rank.
            choice_20m = numpy.argmin(cloud_probs, axis=0)

            # Disagregate and aggregate rank to other resolutions.
            choice_10m = choice_20m.repeat(2, axis=0).repeat(2, axis=1)

            width_60m = int(choice_20m.shape[0] / 3)
            choice_60m = numpy.zeros((width_60m, width_60m)).astype(choice_20m.dtype)
            for x in range(width_60m):
                for y in range(width_60m):
                    block = choice_20m[(3 * x):(3 * x + 3), (3 * y):(3 * y + 3)].ravel()
                    (dat, idx, counts) = numpy.unique(block, return_index=True, return_counts=True)
                    index = idx[numpy.argmax(counts)]
                    mode = block[index]
                    choice_60m[x, y] = mode

            # Choice is at 20 meters, loop thorugh those first.
            CLOUD_IDX1, CLOUD_IDX2 = numpy.indices(choice_20m.shape)
            for band in const.BANDS_20M:
                write_composite(os.path.join(workdir, COMPOSITE_PATH), band, tile_list, choice_20m, CLOUD_IDX1, CLOUD_IDX2, offset_20m, size_20m)

            CLOUD_IDX1, CLOUD_IDX2 = numpy.indices(choice_10m.shape)
            offset_10m = (int(offset_20m[0] * 2), int(offset_20m[1] * 2))
            size_10m = (int(size_20m[0] * 2), int(size_20m[1] * 2))
            for band in const.BANDS_10M:
                write_composite(os.path.join(workdir, COMPOSITE_PATH), band, tile_list, choice_10m, CLOUD_IDX1, CLOUD_IDX2, offset_10m, size_10m)

            CLOUD_IDX1, CLOUD_IDX2 = numpy.indices(choice_60m.shape)
            offset_60m = (int(offset_20m[0] / 3), int(offset_20m[1] / 3))
            size_60m = (int(size_20m[0] / 3), int(size_20m[1] / 3))
            for band in const.BANDS_60M:
                write_composite(os.path.join(workdir, COMPOSITE_PATH), band, tile_list, choice_60m, CLOUD_IDX1, CLOUD_IDX2, offset_60m, size_60m)


def create_tms(workdir, tilez=None):
    """
    Create rasters that aligns with the composite master zoom level at the TMS
    tile scheme.
    """
    for band, band_name in const.BAND_CHOICES:
        print('working on band', band)
        # Open the source raster.
        rst = GDALRaster(os.path.join(workdir, COMPOSITE_PATH, band))
        # Compute the closest TMS zoom level and scale when compared to original.
        closest_z = closest_zoomlevel(rst.scale.x)
        # Compute the index range at the target zoom level.
        geom = OGRGeometry.from_bbox(rst.extent)
        geom.srid = rst.srid
        geom.transform(WEB_MERCATOR_SRID)
        idx = tile_index_range(geom.extent, COMPOSITE_ZOOM)
        # Create one file per zoom level.
        for tilez in range(closest_z, COMPOSITE_ZOOM - 1, -1):
            scale = tile_scale(tilez)
            # Compute the corresponding pixel size of the TMS tile.
            tile_factor = 2 ** (tilez - COMPOSITE_ZOOM)
            size = tile_factor * WEB_MERCATOR_TILESIZE

            for tilex in range(idx[0], idx[2] + 1):
                for tiley in range(idx[1], idx[3] + 1):
                    print('working on tile', '{}-{}-{}, zoom {}'.format(COMPOSITE_ZOOM, tilex, tiley, tilez))
                    # Create target directory.
                    tile_dir = os.path.join(workdir, TMS_PATH, '{}-{}-{}'.format(COMPOSITE_ZOOM, tilex, tiley))
                    try:
                        os.makedirs(tile_dir)
                    except OSError:
                        pass
                    # Get target bounds.
                    bounds = tile_bounds(tilex, tiley, COMPOSITE_ZOOM)
                    # Warp original raster into tile using cubic interpolation.
                    rst.warp({
                        'name': os.path.join(tile_dir, '{}-{}.tif'.format(tilez, band.split('.jp2')[0])),
                        'srid': WEB_MERCATOR_SRID,
                        'driver': 'tif',
                        'datatype': rst.bands[0].datatype(),
                        'origin': (bounds[0], bounds[3]),
                        'width': size,
                        'height': size,
                        'scale': (scale, -scale),
                        'papsz_options': {
                            'compress': 'deflate',
                            'tiled': 'yes',
                        }
                    }, resampling='Cubic')


def cloud_optimize(band, path):
    """
    Optimize geotiffs for cloud.
    """
    if band in const.BANDS_10M:
        levels = '2 4 8 16 32 64'
    elif band in const.BANDS_20M:
        levels = '2 4 8 16 32'
    else:
        levels = '2 4 8 16'
    print('Creating overviews for', path)
    command = 'gdaladdo -r cubic -clean {} {}'.format(path, levels)
    subprocess.run(command, shell=True, check=True)
    print('Creating tiled version of', path)
    tmpfl = os.path.join(os.path.dirname(path), 'co_tmp.tif')
    command = 'gdal_translate {} {} -co TILED=YES -co COMPRESS=DEFLATE -co COPY_SRC_OVERVIEWS=YES'.format(path, tmpfl)
    subprocess.run(command, shell=True, check=True)
    shutil.move(tmpfl, path)


def merge_tms(workdir):
    s3 = boto3.resource('s3')
    for path in glob.glob(os.path.join(workdir, TMS_PATH, '*')):
        tms_key = os.path.basename(path)
        for child in glob.glob(os.path.join(path, '*.tif')):
            band_tif = os.path.basename(child)
            if band_tif == 'rgb.tif':
                continue
            print('Merging', child)
            # Get master file from s3.
            master = '/tmp/master.tif'
            # Try to get master, if it does not exist skip merge and upload
            # child directly.
            s3_obj = s3.Object(COMPOSITE_BUCKET, tms_key + '/{}'.format(band_tif))
            try:
                # Try to download file.
                s3_obj.download_file(master)
            except s3.meta.client.exceptions.ClientError:
                print('no master found, uploading child')
                # If no master exists, upload the new file.
                s3_obj.upload_file(child)
            else:
                print('master found, merging and uploading merge')
                # If master was downloaded successfully, merge it with child.
                child_data = GDALRaster(child).bands[0].data()
                child_mask = child_data != const.SENTINEL_NODATA_VALUE
                master_rst = GDALRaster(master, write=True)
                master_data = master_rst.bands[0].data()
                master_data[child_mask] = child_data[child_mask]
                master_rst.bands[0].data(master_data)
                s3_obj.upload_file(master)


def memory_test(workdir):
    # Get scene list.
    tile_list = glob.glob(os.path.join(os.path.join(workdir, SCENE_PATH), '*'))
    data = []
    for tile in tile_list:
        for band in glob.glob(os.path.join(tile, 'B04.jp2')):
            data.append(GDALRaster(band).bands[0].data())
    return data


def scale_array(arr, vmin, vmax):
    arr = numpy.clip(arr, vmin, vmax)
    return (arr - vmin) / (vmax - vmin)


def generate_rgb(workdir):
    tms_dir = os.path.join(workdir, TMS_PATH, '*')

    for tms in glob.glob(tms_dir):

        print('Creating RGB for', tms)
        red = GDALRaster(os.path.join(tms, '14-' + const.BD4.split('.jp2')[0] + '.tif'))
        gre = GDALRaster(os.path.join(tms, '14-' + const.BD3.split('.jp2')[0] + '.tif'))
        blu = GDALRaster(os.path.join(tms, '14-' + const.BD2.split('.jp2')[0] + '.tif'))

        red_dat = (255 * scale_array(red.bands[0].data(), 0, 3000)).astype('uint8')
        gre_dat = (255 * scale_array(gre.bands[0].data(), 0, 3000)).astype('uint8')
        blu_dat = (255 * scale_array(blu.bands[0].data(), 0, 3000)).astype('uint8')

        GDALRaster({
            'name': os.path.join(tms, 'rgb.tif'),
            'driver': 'tif',
            'srid': red.srid,
            'origin': red.origin,
            'width': red.width,
            'height': red.height,
            'scale': red.scale,
            'datatype': 1,
            'papsz_options': {
                'compress': 'jpeg',
            },
            'bands': [
                {'nodata_value': const.SENTINEL_NODATA_VALUE, 'data': red_dat},
                {'nodata_value': const.SENTINEL_NODATA_VALUE, 'data': gre_dat},
                {'nodata_value': const.SENTINEL_NODATA_VALUE, 'data': blu_dat},
            ]
        })


def run_ecs(mgrs, start, end, vcpus=1, memory=1024, retry=1, stage='production'):
    # Setup job arguments.
    command = {
        'jobName': '-'.join((mgrs, start, end))[:128],
        'jobQueue': 'tesselo-{stage}'.format(stage=stage),
        'jobDefinition': 'tesselo-{stage}'.format(stage=stage),
        'containerOverrides': {
            'command': [
                'python', '/code/apps/sentinel/single_composite_task.py',
                '--workdir', '/tmp',
                '--start', start,
                '--end', end,
                '--mgrs', mgrs,
                '--download',
                '--composite',
                '--tms',
                '--merge'
            ],
            'vcpus': vcpus,
            'memory': memory,
            'environment': [
                {'name': 'AWS_ACCESS_KEY_ID', 'value': os.environ.get('AWS_ACCESS_KEY_ID')},
                {'name': 'AWS_SECRET_ACCESS_KEY', 'value': os.environ.get('AWS_SECRET_ACCESS_KEY')},
                {'name': 'PYTHONPATH', 'value': '/code/apps'},
            ]
        },
        'retryStrategy': {
            'attempts': retry
        }
    }

    # Instanciate batch client and submit job.
    client = boto3.client('batch', region_name='eu-west-1')
    return client.submit_job(**command)


def confirm(message):
    # Ask for user confirmation.
    sys.stdout.write('Type "yes" to confirm you want to {} -- '.format(message))
    if input().lower() != 'yes':
        sys.stdout.write('The answer was not "yes", aborted operation')
        return False
    else:
        return True


if __name__ == "__main__":
    argparser = argparse.ArgumentParser(description='Create a composite over a MGRS tile for a date range.')

    argparser.add_argument('--workdir', required=True, help='Speciy the working directory.')
    argparser.add_argument('--mgrs', required=False, help='Speciy the MGRS tile as string (for example 29SMD)')
    argparser.add_argument('--start', required=False, help='Speciy the start date for composite (for example 2018-05-01)')
    argparser.add_argument('--end', required=False, help='Speciy the end date for composite (for example 2018-05-10)')
    argparser.add_argument('--download', action='store_const', const=True, default=False, help='Run the download step.')
    argparser.add_argument('--composite', action='store_const', const=True, default=False, help='Run the build composite step.')
    argparser.add_argument('--tms', action='store_const', const=True, default=False, help='Run the transform to TMS step.')
    argparser.add_argument('--merge', action='store_const', const=True, default=False, help='Merge data into S3 bucket.')
    argparser.add_argument('--rgb', action='store_const', const=True, default=False, help='Run the create RGB step.')
    argparser.add_argument('--ecs', action='store_const', const=True, default=False, help='Run the entire composite build on AWS Batch.')

    args = argparser.parse_args()

    if args.download:
        print('Running download')
        get_data(args.mgrs, args.start, args.end, args.workdir)

    if args.composite:
        print('Running composite build')
        create_composite(args.workdir)

    if args.tms:
        print('Running tms creation')
        create_tms(args.workdir)

    if args.merge:
        print('Running tms merge')
        merge_tms(args.workdir)

    if args.rgb:
        print('Running RGB creation')
        generate_rgb(args.workdir)

    if args.ecs:
        if confirm('Run this composite remotely'):
            run_ecs(args.mgrs, args.start, args.end)
