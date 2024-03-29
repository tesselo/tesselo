import datetime
import glob
import json
import logging
import os
import pathlib
import shutil
import subprocess
import traceback

import boto3
import numpy
import sentry_sdk
import structlog
from dateutil import parser
from django.conf import settings
from django.contrib.gis.gdal import Envelope, GDALRaster, OGRGeometry
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from raster.models import RasterLayer
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import tile_bounds
from raster_aggregation.models import AggregationArea

from jobs import ecs
from report.tasks import push_reports
from sentinel import const
from sentinel.clouds.algorithms import Clouds
from sentinel.clouds.utils import sun
from sentinel.models import (
    BucketParseLog, Composite, CompositeBuild, CompositeBuildSchedule, CompositeTile, MGRSTile, SentinelTile,
    SentinelTileAggregationLayer, SentinelTileBand, SentinelTileSceneClass
)
from sentinel.utils import aggregate_tile, disaggregate_tile, get_raster_tile, locally_parse_raster, write_raster_tile
from sentinel_1 import const as s1const
from sentinel_1.models import Sentinel1Tile

logger = structlog.get_logger('django_structlog')

boto3.set_stream_logger('boto3', logging.ERROR)


def drive_sentinel_bucket_parser():
    for utm_zone in range(1, const.NUMBER_OF_UTM_ZONES + 1):
        if BucketParseLog.objects.filter(utm_zone=utm_zone, status__in=(BucketParseLog.PENDING, BucketParseLog.PROCESSING)).exists():
            logger.info('UTM Zone {} is currently parsing, no new task scheduled.'.format(utm_zone))
        else:
            # Create bucket parse log.
            log = BucketParseLog.objects.create(
                utm_zone=utm_zone,
                status=BucketParseLog.PENDING,
                scheduled=timezone.now(),
            )
            ecs.sync_sentinel_bucket_utm_zone(utm_zone)
            log.write('Scheduled parsing utm zone "{0}".'.format(utm_zone))


def sync_sentinel_bucket_utm_zone(utm_zone):
    """
    Synchronize the local database of sentinel scenes with the sentinel S3
    bucket.
    """
    # Get or create bucket parse log.
    log = BucketParseLog.objects.filter(
        utm_zone=utm_zone,
        status__in=(BucketParseLog.PENDING, BucketParseLog.PROCESSING),
    ).first()

    if not log:
        now = timezone.now()
        log = BucketParseLog.objects.create(
            utm_zone=utm_zone,
            status=BucketParseLog.PROCESSING,
            scheduled=now,
            start=now,
        )
    elif log.status == BucketParseLog.PROCESSING:
        # Abort if this utm zone is already processing.
        return

    # Update start time and log.
    log.start = timezone.now()
    log.write('Started parsing utm zone "{0}".'.format(utm_zone), BucketParseLog.PROCESSING)

    # Initiate boto session.
    client = boto3.client(const.CLIENT_TYPE)
    paginator = client.get_paginator(const.PAGINATOR_LOOKUP)
    prefix = const.PAGINATOR_BASE_PREFIX
    prefix += str(utm_zone) + '/'
    iterator = paginator.paginate(Bucket=const.BUCKET_NAME, Prefix=prefix, RequestPayer='requester')
    filtered_iterator = iterator.search(const.TILE_INFO_FILE_JMES_SEARCH)

    # Iteratively follow all keys.
    counter = 0
    for tileinfo_key in filtered_iterator:
        # Get prefix for this tile from tileinfo key.
        tile_prefix = tileinfo_key.split(const.TILE_INFO_FILE)[0]

        # Skip this tile if it's already registered.
        if SentinelTile.objects.filter(prefix=tile_prefix).exists():
            continue

        counter += 1
        try:
            ingest_tile_from_prefix(tile_prefix, client)
            log.write('Registered ' + tile_prefix)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            log.write('Failed registering ' + tile_prefix + traceback.format_exc())

    # Log the end of the parsing process
    log.end = timezone.now()
    log.write('Finished parsing, {0} tiles created.'.format(counter), BucketParseLog.FINISHED)


def ingest_tile_from_prefix(tile_prefix, client=None):
    # Instanciate client. The client can be passed mainly to fix stubber during
    # tests.
    if not client:
        client = boto3.client(const.CLIENT_TYPE)

    # Construct TileInfo file key.
    tileinfo_key = tile_prefix + const.TILE_INFO_FILE

    # Get tile info json data.
    tileinfo = client.get_object(Key=tileinfo_key, Bucket=const.BUCKET_NAME, RequestPayer='requester')
    tileinfo = json.loads(tileinfo.get(const.TILEINFO_BODY_KEY).read().decode())

    # Get or create MGRS tile for this sentinel tile.
    mgrs, created = MGRSTile.objects.get_or_create(
        grid_square=tileinfo['gridSquare'],
        utm_zone=tileinfo['utmZone'],
        latitude_band=tileinfo['latitudeBand'],
    )

    # For new MGRS tiles, set geometry from tile info.
    if created:
        mgrs.geom = OGRGeometry(json.dumps(tileinfo['tileGeometry'])).geos
        mgrs.save()

    if 'tileGeometry' in tileinfo:
        tile_geom = OGRGeometry(str(tileinfo['tileGeometry'])).geos

        if not isinstance(tile_geom, Polygon):
            tile_geom = Polygon(tile_geom, srid=tile_geom.srid)

        # Set geom to none if tile data geom is not valid.
        if not tile_geom.valid:
            tile_geom = None
    else:
        tile_geom = None

    # Get tile data geometry and make sure its a multi polygon.
    if 'tileDataGeometry' in tileinfo:
        tile_data_geom = OGRGeometry(str(tileinfo['tileDataGeometry'])).geos

        if not isinstance(tile_data_geom, MultiPolygon):
            tile_data_geom = MultiPolygon(tile_data_geom, srid=tile_data_geom.srid)

        # Set geom to none if tile data geom is not valid.
        if not tile_data_geom.valid:
            tile_data_geom = None
    else:
        tile_data_geom = None

    # Assume data coverage is zero if info is not available.
    data_coverage_percentage = tileinfo.get('dataCoveragePercentage', 0)

    # Compute sun angle at center of tile.
    cen = mgrs.geom.centroid.transform(4326, clone=True)
    date = parser.parse(tileinfo['timestamp'])
    alt, azim = sun(date, cen.y, cen.x)

    # Register tile, log error if creation failed.
    return SentinelTile.objects.create(
        prefix=tile_prefix,
        datastrip=tileinfo['datastrip']['id'],
        product_name=tileinfo['productName'],
        mgrstile=mgrs,
        tile_geom=tile_geom,
        tile_data_geom=tile_data_geom,
        collected=date,
        cloudy_pixel_percentage=tileinfo['cloudyPixelPercentage'],
        data_coverage_percentage=data_coverage_percentage,
        angle_azimuth=azim,
        angle_altitude=alt,
    )


def get_aggregation_area_scenes(aggregationarea_id):
    """
    Get all available scenes for each aggregation area in the system.
    """
    area = AggregationArea.objects.get(id=aggregationarea_id)

    # Get tiles that intersect with the aggregation area, but are not
    # at the utm zone boundaries.
    # TODO: repair the boundary geometries instead of filtering them.
    tiles = SentinelTile.objects.filter(
        tile_data_geom__intersects=area.geom,
    ).exclude(
        prefix__startswith='tiles/1/',
    ).exclude(
        prefix__startswith='tiles/60/',
    ).values_list('id', flat=True)

    for tile_id in tiles:
        # Register tile for this aggregationarea.
        SentinelTileAggregationLayer.objects.get_or_create(
            sentineltile_id=tile_id,
            aggregationlayer_id=area.aggregationlayer_id,
        )


@receiver(post_save, sender=AggregationArea)
def trigger_scene_ingestion(sender, instance, **kwargs):
    get_aggregation_area_scenes(instance.id)


def get_range_tiles(sentineltiles, tilex, tiley, tilez):
    """
    Return a RasterTile queryset of tiles for the given indices.
    """
    if tilez == const.ZOOM_LEVEL_60M:
        bnds = const.BANDS_60M
    elif tilez == const.ZOOM_LEVEL_20M:
        bnds = const.BANDS_20M
    else:
        bnds = const.BANDS_10M

    # Return data as tuples of scene, band number and pixel values.
    tiles = []
    for sentineltile in sentineltiles:
        for sentineltileband in sentineltile.sentineltileband_set.filter(band__in=bnds):
            tile = get_raster_tile(sentineltileband.layer_id, tilez, tilex, tiley)
            if not tile:
                continue
            tiles.append((sentineltile.prefix, sentineltileband.band, tile.bands[0].data()))

        if tilez == const.ZOOM_LEVEL_20M:
            if not hasattr(sentineltile, 'sentineltilesceneclass'):
                continue
            tile = get_raster_tile(sentineltile.sentineltilesceneclass.layer_id, tilez, tilex, tiley)
            if not tile:
                continue
            tiles.append((sentineltile.prefix, const.SCL, tile.bands[0].data()))

    return tiles


def compositetile_stacks(ctile):
    """
    Iterator to provide scene level band stacks for all xyz tiles that
    are within one CompositeTile.
    """
    logger.info('Creating Tiles for Layer "{0}" at {1}/{2}/{3}'.format(
        ctile.composite.name,
        ctile.tilez,
        ctile.tilex,
        ctile.tiley,
    ))
    # Get queryset for sentineltiles within the composite date range.
    sentineltiles = ctile.composite.get_sentineltiles()

    # Compute indexrange for this higher level tile.
    indexrange = ctile.index_range(const.ZOOM_LEVEL_60M)

    # Loop through tiles at 60m that intersect with bounding box.
    for tilex60 in range(indexrange[0], indexrange[2] + 1):
        for tiley60 in range(indexrange[1], indexrange[3] + 1):
            # Limit sentineltiles to those overlapping with the 60m tile.
            bounds60 = tile_bounds(tilex60, tiley60, const.ZOOM_LEVEL_60M)
            # Get tile bounding box as ewkt.
            bounds60 = 'SRID={0};{1}'.format(WEB_MERCATOR_SRID, Envelope(bounds60).wkt)
            # Filter sentinel scenes that overlap with this tile boundaries.
            sentineltiles60 = sentineltiles.filter(tile_data_geom__intersects=bounds60).only('prefix')
            # Prefetch related objects.
            sentineltiles60 = sentineltiles60.select_related('sentineltilesceneclass').prefetch_related('sentineltileband_set')

            tiles60 = get_range_tiles(sentineltiles60, tilex60, tiley60, const.ZOOM_LEVEL_60M)
            if not len(tiles60):
                continue

            # Loop through children tiles at 20m.
            for tilex20 in range(tilex60 * const.M26, (tilex60 + 1) * const.M26):
                for tiley20 in range(tiley60 * const.M26, (tiley60 + 1) * const.M26):

                    tiles20 = get_range_tiles(sentineltiles60, tilex20, tiley20, const.ZOOM_LEVEL_20M)
                    if not len(tiles20):
                        continue

                    # Loop through children tiles at 10m.
                    for tilex10 in range(tilex20 * const.M12, (tilex20 + 1) * const.M12):
                        for tiley10 in range(tiley20 * const.M12, (tiley20 + 1) * const.M12):

                            tiles10 = get_range_tiles(sentineltiles60, tilex10, tiley10, const.ZOOM_LEVEL_10M)
                            if not len(tiles10):
                                continue

                            # Warp larger 60m and 20m rasters to 10m level.
                            offset60x = (tilex10 - const.M16 * tilex60) * WEB_MERCATOR_TILESIZE / const.M16
                            offset60y = (tiley10 - const.M16 * tiley60) * WEB_MERCATOR_TILESIZE / const.M16
                            tiles60_warped = [(x[0], x[1], disaggregate_tile(x[2], const.M16, offset60x, offset60y)) for x in tiles60]

                            offset20x = (tilex10 - const.M12 * tilex20) * WEB_MERCATOR_TILESIZE / const.M12
                            offset20y = (tiley10 - const.M12 * tiley20) * WEB_MERCATOR_TILESIZE / const.M12
                            tiles20_warped = [(x[0], x[1], disaggregate_tile(x[2], const.M12, offset20x, offset20y)) for x in tiles20]

                            # Create a stack for each scene.
                            stacks = {}
                            stacks_length = {}
                            for scene, band, tile in (tiles60_warped + tiles20_warped + tiles10):
                                if scene not in stacks:
                                    stacks[scene] = {}
                                    stacks_length[scene] = 1
                                else:
                                    stacks_length[scene] += 1
                                stacks[scene][band] = tile

                            # Drop incomplete stacks, total number of bands plus SCL layer.
                            for key, count in stacks_length.items():
                                if count != const.NR_OF_BANDS + 1:
                                    del stacks[key]

                            # Skp if no complete stack is available for this tile.
                            if not len(stacks):
                                continue

                            # Return stacks as list the scene id is no longer
                            # relevant after this.
                            yield tilex10, tiley10, list(stacks.values())


def process_compositetile_s1(ctile, rasterlayer_lookup):
    """
    Construct max zoom level raster tiles for S1 input.
    """
    # Compute index range for the 10M zoom level over the compositetile.
    indexrange = ctile.index_range(const.ZOOM_LEVEL_10M)
    # Get list of scenes for this compoistetile.
    bounds = tile_bounds(ctile.tilex, ctile.tiley, ctile.tilez)
    bounds = 'SRID={0};{1}'.format(WEB_MERCATOR_SRID, Envelope(bounds).wkt)
    sentinel1tiles = ctile.composite.get_sentinel1tiles().filter(
        status=Sentinel1Tile.FINISHED,
        footprint__intersects=bounds,
    )
    # Get tiles from available ingested S1 scenes.
    counter = 0
    for tilex in range(indexrange[0], indexrange[2] + 1):
        for tiley in range(indexrange[1], indexrange[3] + 1):
            # Prepare result dict.
            result = {dvband: None for dvband in s1const.POLARIZATION_DV_BANDS}
            # Loop through sentinel 1 tiles in order of appearance until all
            # pixels are populated, or all available scenes have been exhausted.
            for stile in sentinel1tiles:
                for dvband in s1const.POLARIZATION_DV_BANDS:
                    # Get tile for this scene.
                    sband = stile.sentinel1tileband_set.get(band=dvband)
                    tile = get_raster_tile(sband.layer_id, const.ZOOM_LEVEL_10M, tilex, tiley)
                    if not tile:
                        break
                    tile = tile.bands[0].data()
                    # Populate result array with new pixels.
                    if result[dvband] is None:
                        # Set result to be the first tile.
                        result[dvband] = tile
                    else:
                        # Replace missing pixels with pixels from additional scene.
                        missing_pixels = result[dvband] == s1const.SENTINEL_1_NODATA_VALUE
                        if numpy.sum(missing_pixels) > 0:
                            result[dvband][missing_pixels] = tile[missing_pixels]
                    # Replace very dark pixels if possible. Pixels that are
                    # below a threshold are likely to be dark scene edge
                    # artifact pixels.
                    artifact_pixels = result[dvband] < s1const.DARK_SCENE_EDGE_THRESHOLD
                    result[dvband][artifact_pixels] = numpy.maximum.reduce([result[dvband], tile])[artifact_pixels]
                # Check if any nodata pixels are remaining, assuming that if one
                # band is fully populated, the other one is as well. If fully
                # populated, don't search for more S1 scenes and go to next tile.
                if s1const.SENTINEL_1_NODATA_VALUE not in result[s1const.POLARIZATION_DV_BANDS[0]]:
                    break

            # Ignore this tile if no data was found for it.
            if any(val is None for val in result.values()):
                continue

            # Update results dict with data, using a random name for the in
            # memory raster.
            for band, data in result.items():
                write_raster_tile(
                    rasterlayer_lookup[band],
                    data,
                    const.ZOOM_LEVEL_10M,
                    tilex,
                    tiley,
                    nodata_value=s1const.SENTINEL_1_NODATA_VALUE,
                    datatype=s1const.SENTINEL_1_DATA_TYPE,
                    merge_with_existing=False,
                )

            # Log progress.
            counter += 1
            if counter % 100 == 0:
                ctile.write('{count} S1 Tiles Created, currently at ({x}, {y}).'.format(count=counter, x=tilex, y=tiley))


def process_compositetile_s2(ctile, rasterlayer_lookup):
    """
    Construct max zoom level raster tiles for S2 input.
    """
    # Get cloud algorithm.
    clouds = Clouds(ctile)
    ctile.write('Using S2 cloud removal algorithm {}'.format(ctile.get_version_string()))

    # Loop over all TMS tiles in a given zone and get band stacks for available
    # scenes in that tile.
    counter = 0
    for x, y, stacks in compositetile_stacks(ctile):
        # Compute the cloud probabilities for each avaiable scene band stack.
        cloud_probs = [clouds.clouds(stack) for stack in stacks]

        # Compute an array of scene indices with the lowest cloud probability.
        selector_index = numpy.argmin(cloud_probs, axis=0)

        # Compute mask for pixels where all stacks are over the exclude value.
        exclude = numpy.min(cloud_probs, axis=0) >= const.EXCLUDE_VALUE

        # Loop over all bands.
        for key in const.ALL_BANDS:
            # Merge scene tiles for this band into a composite tile using the selector index.
            bnds = numpy.array([stack[key] for stack in stacks])

            # Construct final composite band array from selector index.
            composite_data = bnds[selector_index, const.CLOUD_IDX1, const.CLOUD_IDX2]

            # Exclude bad pixels.
            composite_data[exclude] = const.SENTINEL_NODATA_VALUE

            # Ensure datatype.
            if key == const.SCL:
                datatype = 1
                composite_data = composite_data.astype('uint8')
            else:
                datatype = 2
                composite_data = composite_data.astype('uint16')

            # Update results dict with data, using a random name for the in
            # memory raster.
            write_raster_tile(
                rasterlayer_lookup[key],
                composite_data,
                const.ZOOM_LEVEL_10M,
                x,
                y,
                datatype=datatype,
                merge_with_existing=False,
            )

        # Log progress.
        counter += 1
        if counter % 100 == 0:
            ctile.write('{count} S2 Tiles Created, currently at ({x}, {y}).'.format(count=counter, x=x, y=y))


def process_compositetile(compositetile_id):
    """
    Build a cloud free unified base layer for a given areas of interest and for
    each sentinel band.
    """
    ctile = CompositeTile.objects.get(id=compositetile_id)
    ctile.start = timezone.now()
    ctile.end = None
    ctile.write('Starting to build composite at max zoom level.', CompositeTile.PROCESSING)

    # Get the list of master layers for all 13 bands.
    rasterlayer_lookup = ctile.composite.rasterlayer_lookup

    if ctile.include_sentinel_1:
        rasterlayer_lookup_s1 = {key: val for key, val in rasterlayer_lookup.items() if key in s1const.POLARIZATION_DV_BANDS}
        process_compositetile_s1(ctile, rasterlayer_lookup_s1)

    if ctile.include_sentinel_2:
        rasterlayer_lookup_s2 = {key: val for key, val in rasterlayer_lookup.items() if key in const.ALL_BANDS}
        process_compositetile_s2(ctile, rasterlayer_lookup_s2)

    # Start pyramid building phase.
    ctile.write('Finished building composite tile at max zoom level, starting Pyramid.')

    # Loop over all zoom levels to construct pyramid.
    zoomrange = reversed(range(1, const.ZOOM_LEVEL_10M + 1))
    for zoom in zoomrange:
        # Compute index range for the zone of interest.
        factor = 2 ** (zoom - const.ZOOM_LEVEL_60M)
        indexrange = [int(idx * factor) for idx in ctile.index_range(const.ZOOM_LEVEL_60M)]
        if zoom > const.ZOOM_LEVEL_60M:
            indexrange[2] += factor - 1
            indexrange[3] += factor - 1

        # Make sure the index ranges start with a multiple of 2 to avoid edge
        # effects when aggregating.
        if indexrange[0] % 2 == 1:
            indexrange[0] -= 1

        if indexrange[1] % 2 == 1:
            indexrange[1] -= 1

        msg = 'Creating World Pyramid at Zoom {0} for Index Range {1}.'.format(
            zoom - 1,
            [idx // 2 for idx in indexrange],
        )
        ctile.write(msg)

        # Loop over composite band tiles in blocks of four.
        for tilex in range(indexrange[0], indexrange[2] + 1, 2):
            for tiley in range(indexrange[1], indexrange[3] + 1, 2):
                # Aggregate tiles for each composite band.
                for band_name, rasterlayer_id in rasterlayer_lookup.items():
                    result = []
                    none_found = True
                    is_S1 = band_name in s1const.POLARIZATION_DV_BANDS
                    # Determine data type.
                    if is_S1:
                        dtype = numpy.float32
                    elif band_name == const.SCL:
                        dtype = numpy.uint8
                    else:
                        dtype = numpy.uint16
                    # Read each tile in the block of 2x2.
                    for idx, dat in enumerate(((0, 0), (1, 0), (0, 1), (1, 1))):
                        tile = get_raster_tile(rasterlayer_id, zoom, tilex + dat[0], tiley + dat[1])
                        if tile:
                            none_found = False
                            agg = tile.bands[0].data()
                        else:
                            agg = numpy.zeros((WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE), dtype=dtype)
                        result.append(agg)
                    # Continue if no tile could be found for this 2x2 block.
                    if none_found:
                        continue
                    # Combine the tiles to a new full tile.
                    upper = numpy.append(result[0], result[1], axis=1)
                    lower = numpy.append(result[2], result[3], axis=1)
                    result = numpy.append(upper, lower, axis=0)
                    # Aggregate tile by a factor of two to match lower zoom level.
                    result = aggregate_tile(result, target_dtype=dtype)
                    # Write pixels into a tile, using dtype and nodata specs of
                    # each satellite system.
                    if is_S1:
                        nodata_value = s1const.SENTINEL_1_NODATA_VALUE
                        datatype = 6
                    else:
                        nodata_value = const.SENTINEL_NODATA_VALUE
                        datatype = 1 if band_name == const.SCL else 2
                    write_raster_tile(rasterlayer_id, result, zoom - 1, tilex // 2, tiley // 2, nodata_value, datatype)

    ctile.end = timezone.now()
    ctile.write('Finished building composite tile.', CompositeTile.FINISHED)

    # Run callback for composite builds, allow disabling callbacks when testing.
    for cbuild in ctile.compositebuild_set.all():
        composite_build_callback(cbuild.id)


SEN2COR_CMD_TMPL = '/Sen2Cor-2.4.0-Linux64/bin/L2A_Process {product_path}'


def process_l2a(sentineltile_id):
    # Open sentinel tile instance.
    tile = SentinelTile.objects.get(id=sentineltile_id)

    # Don't duplicate the effort.
    if tile.status in (SentinelTile.PROCESSING, SentinelTile.FINISHED, SentinelTile.BROKEN):
        tile.write('Status is {}, aborted additional L2A update.'.format(tile.status))
        return
    else:
        tile.write('Started processing tile for L2A upgrade.', SentinelTile.PROCESSING)

    # Check if L2A product already exists.
    s3 = boto3.resource('s3')
    obj = s3.Object('sentinel-s2-l2a', '{prefix}productInfo.json'.format(prefix=tile.prefix))
    try:
        obj.get(RequestPayer='requester')
    except s3.meta.client.exceptions.NoSuchKey:
        # Get fallback SRID. This SRID will be used if Sen2Cor fails to properly set
        # the srid of its output rasters.
        client = boto3.client(const.CLIENT_TYPE)
        tileinfo = client.get_object(Key=f'{tile.prefix}tileInfo.json', Bucket=const.BUCKET_NAME, RequestPayer='requester')
        tileinfo = json.loads(tileinfo.get(const.TILEINFO_BODY_KEY).read().decode())
        fallback_srid = int(tileinfo['tileGeometry']['crs']['properties']['name'].split(':')[-1])
        run_sen2cor(tile)
    else:
        fallback_srid = None
        download_l2a(tile)

    # Ingest the resulting rasters as tiles.
    for band, zoom, rasterlayer_id in generate_bands_and_sceneclass(tile):
        bandpath = '/rasterwd/products/{tile_id}/{band}'.format(tile_id=tile.id, band=band)
        try:
            tmpdir = '/rasterwd/products/{tile_id}/tmp'.format(tile_id=tile.id)
            pathlib.Path(tmpdir).mkdir(parents=True, exist_ok=True)
            locally_parse_raster(tmpdir, rasterlayer_id, bandpath, zoom, fallback_srid=fallback_srid)
        except Exception as e:
            sentry_sdk.capture_exception(e)
            tile.write('Failed processing band {}. {}'.format(band, traceback.format_exc()), SentinelTile.FAILED)
            shutil.rmtree('/rasterwd/products/{}'.format(tile.id), ignore_errors=True)
            raise

        tile.write('Finished processing band {}'.format(band))

    # Remove main product files.
    shutil.rmtree('/rasterwd/products/{}'.format(tile.id), ignore_errors=True)

    # Update tile status.
    tile.write('Finished L2A upgrade.', SentinelTile.FINISHED, const.LEVEL_L2A)

    # Run callbacks to continue build chain.
    for cbuild in tile.compositebuild_set.filter(status=CompositeBuild.INGESTING_SCENES):
        composite_build_callback(cbuild.id)


def generate_bands_and_sceneclass(tile):
    """
    Ensure SentinelTileBand and SentinelTileSceneClass objects exist.
    """
    for filename, description in const.BAND_CHOICES:
        # Fix zoom level by band to ensure consistency.
        if filename in const.BANDS_10M:
            zoom = const.ZOOM_LEVEL_10M
        elif filename in const.BANDS_20M:
            zoom = const.ZOOM_LEVEL_20M
        else:
            zoom = const.ZOOM_LEVEL_60M

        # Check if this band already exists.
        band = SentinelTileBand.objects.filter(band=filename, tile=tile).first()

        if not band:
            # Create new raster layer and register it as sentinel band.
            layer = RasterLayer.objects.create(
                name=tile.prefix + filename,
                datatype=RasterLayer.CONTINUOUS,
                nodata=const.SENTINEL_NODATA_VALUE,
                max_zoom=zoom,
                build_pyramid=True,
                store_reprojected=False,
            )

            # Make sentinel bands available to all users.
            layer.publicrasterlayer.public = True
            layer.publicrasterlayer.save()

            # Register raster layer as sentinel tile band.
            band = SentinelTileBand.objects.create(
                layer=layer,
                band=filename,
                tile=tile,
            )

        yield filename, zoom, band.layer.id

    if not hasattr(tile, 'sentineltilesceneclass'):
        # Create new raster layer.
        layer = RasterLayer.objects.create(
            name=tile.prefix + const.SCL,
            datatype=RasterLayer.CATEGORICAL,
            nodata=const.SENTINEL_NODATA_VALUE,
            max_zoom=const.ZOOM_LEVEL_20M,
            build_pyramid=True,
            store_reprojected=False,
        )

        # Make scene class layers available to all users.
        layer.publicrasterlayer.public = True
        layer.publicrasterlayer.save()

        # Register raster layer as sentinel scene class.
        SentinelTileSceneClass.objects.create(layer=layer, tile=tile)
        sceneclass_layer_id = layer.id
    else:
        sceneclass_layer_id = tile.sentineltilesceneclass.layer_id

    yield const.SCL, const.ZOOM_LEVEL_20M, sceneclass_layer_id


def download_l2a(tile):
    tile.write('Found existing L2A product, downloading data.')
    # Prepare data dirs.
    os.makedirs('/rasterwd/products/{}'.format(tile.id))
    # Download each band and scene class.
    for band, resolution in const.BAND_RESOLUTIONS.items():
        # Band 10 is not kept in L2A as it does not contain surface
        # information (its fully absorbed in atmosphere, any reflectance
        # is due to atmospheric scattering).
        if band == const.BD10:
            bucket = 'sentinel-s2-l1c'
            prefix = '{prefix}{band}'.format(
                prefix=tile.prefix,
                band=band,
            )
        else:
            bucket = 'sentinel-s2-l2a'
            prefix = '{prefix}R{resolution}m/{band}'.format(
                prefix=tile.prefix,
                resolution=resolution,
                band=band,
            )
        dest = '/rasterwd/products/{tile_id}/{band}'.format(
            tile_id=tile.id,
            band=band,
        )
        tile.write('Downloading file ' + band)
        s3 = boto3.resource('s3')
        try:
            s3.Object(bucket, prefix).download_file(dest, ExtraArgs={'RequestPayer': 'requester'})
        except Exception as e:
            sentry_sdk.capture_exception(e)
            shutil.rmtree('/rasterwd/products/{tile_id}'.format(tile_id=tile.id), ignore_errors=True)
            tile.write('Failed download of L2A data.', SentinelTile.FAILED)
            raise

        # L2A data in sentinel-s2-l2a bucket does not have an srid and wrong
        # geotransform params. So move data to tif with correct specs.
        original_data = GDALRaster(dest).bands[0].data()
        original_datatype = GDALRaster(dest).bands[0].datatype()
        original_extent = tile.tile_geom.transform(tile.srid, clone=True).extent
        # Overwrite original file, to keep naming convention (this writes tif
        # files with jp2 extension).
        GDALRaster({
            'name': dest,
            'srid': tile.srid,
            'driver': 'tif',
            'datatype': original_datatype,
            'origin': (original_extent[0], original_extent[3]),
            'width': original_data.shape[1],
            'height': original_data.shape[0],
            'scale': [resolution, -resolution],
            'bands': [{'nodata_value': const.SENTINEL_NODATA_VALUE, 'data': original_data}],
        })
    tile.write('Finished L2A product download.')


def run_sen2cor(tile):
    """
    Get L1C data and run Sen2Cor to upgrade to L2A.
    """
    # SentinelHub library is only installed on workers.
    from sentinelhub import AwsProductRequest

    # Download the scene.
    tile.write('Starting download of product data.')
    try:
        product_request = AwsProductRequest(
            product_id=tile.product_name,
            data_folder='/rasterwd/products/{tile_id}'.format(tile_id=tile.id),
            safe_format=True,
            tile_list=[tile.mgrstile.code],
        )
        product_request.save_data()
    except Exception as e:
        sentry_sdk.capture_exception(e)
        shutil.rmtree('/rasterwd/products/{tile_id}'.format(tile_id=tile.id), ignore_errors=True)
        tile.write('Failed download of product data.', SentinelTile.FAILED)
        raise
    tile.write('Finished download of product data.')
    # Construct Sen2Cor command.
    product_path = glob.glob('/rasterwd/products/{}/*.SAFE'.format(tile.id))[0]
    sen2cor_cmd = SEN2COR_CMD_TMPL.format(product_path=product_path)

    # Apply atmoshperic correction.
    tile.write('Starting Sen2Cor algorithm.')
    try:
        subprocess.run(sen2cor_cmd, shell=True, check=True)
    except Exception as e:
        sentry_sdk.capture_exception(e)
        shutil.rmtree('/rasterwd/products/{tile_id}'.format(tile_id=tile.id), ignore_errors=True)
        tile.write('Failed applying Sen2Cor algorithm.', SentinelTile.FAILED)
        raise

    # Move files to parent dir.
    for band, resolution in const.BAND_RESOLUTIONS.items():
        # Band 10 is not kept in L2A as it does not contain surface
        # information (its fully absorbed in atmosphere, any reflectance
        # is due to atmospheric scattering).
        if band == const.BD10:
            glob_pattern = '/rasterwd/products/{tile_id}/S2*_MSIL1C*.SAFE/GRANULE/**/*{band}'.format(
                tile_id=tile.id,
                band=band,
            )
            bandpath = glob.glob(glob_pattern, recursive=True)
        else:
            glob_pattern = '/rasterwd/products/{tile_id}/S2*_MSIL2A*.SAFE/GRANULE/**/*{band}*{resolution}m.jp2'.format(
                tile_id=tile.id,
                band=band.split('.jp2')[0],
                resolution=resolution,
            )
            bandpath = glob.glob(glob_pattern, recursive=True)

        if not len(bandpath):
            tile.write('Output for band {} of Sen2Cor algorithm not found. This is likely related to a Sen2Cor failure.'.format(band), SentinelTile.FAILED)
            shutil.rmtree('/rasterwd/products/{tile_id}'.format(tile_id=tile.id), ignore_errors=True)
            raise ValueError('Could not find band {}'.format(band))

        shutil.move(bandpath[0], '/rasterwd/products/{tile_id}/{band}'.format(tile_id=tile.id, band=band))

    # Remove unnecessary data.
    glob_pattern = '/rasterwd/products/{tile_id}/S2*.SAFE'.format(tile_id=tile.id)
    for path in glob.glob(glob_pattern):
        shutil.rmtree(path, ignore_errors=True)

    tile.write('Finished applying Sen2Cor algorithm.')


def composite_build_callback(compositebuild_id, initiate=False, rebuild=False):
    """
    Initiate and update composite builds.
    """
    compositebuild = CompositeBuild.objects.get(id=compositebuild_id)

    # Initiate the compositebuild related objects if requested.
    if initiate:
        compositebuild.preflight(initiate=True)

    # Enforce re-building of composite tiles.
    if rebuild:
        for ctile in compositebuild.compositetiles.filter(status__in=(CompositeTile.FINISHED, CompositeTile.FAILED)):
            ctile.write('Rebuilding composite tile, setting status to unprocessed.', CompositeTile.UNPROCESSED)

    still_ingesting_tiles = False

    # Flag to check scene status. If non-finished or non-broken tiles exist,
    # ingestion is assumed to be incomplete.
    s1_scene_ingestion_incomplete = compositebuild.sentinel1tiles.exclude(status__in=(Sentinel1Tile.FINISHED, Sentinel1Tile.BROKEN)).exists()
    if compositebuild.include_sentinel_1 and s1_scene_ingestion_incomplete:
        # Ensure compsitebuild status is "ingesting scenes".
        if compositebuild.status != CompositeBuild.INGESTING_SCENES:
            compositebuild.status = CompositeBuild.INGESTING_SCENES
            compositebuild.save()
        # Call the L2A upgrader for the set of sentinel tiles that are still
        # unprocessed or have failed processing.
        sentinel1tiles = compositebuild.sentinel1tiles.filter(
            status__in=(Sentinel1Tile.FAILED, Sentinel1Tile.UNPROCESSED)
        )

        for stile in sentinel1tiles:
            # Log scheduling of scene ingestion.
            stile.scheduled = timezone.now()
            stile.write('Scheduled scene ingestion, waiting for worker availability.', SentinelTile.PENDING)
            ecs.snap_terrain_correction(stile.id)

        still_ingesting_tiles = True

    s2_scene_ingestion_incomplete = compositebuild.sentineltiles.exclude(status__in=(SentinelTile.FINISHED, SentinelTile.BROKEN)).exists()

    if compositebuild.include_sentinel_2 and s2_scene_ingestion_incomplete:
        # Ensure compsitebuild status is "ingesting scenes".
        if compositebuild.status != CompositeBuild.INGESTING_SCENES:
            compositebuild.status = CompositeBuild.INGESTING_SCENES
            compositebuild.save()
        # Call the L2A upgrader for the set of sentinel tiles that are still
        # unprocessed or have failed processing.
        sentineltiles = compositebuild.sentineltiles.filter(
            status__in=(SentinelTile.FAILED, SentinelTile.UNPROCESSED)
        )
        for stile in sentineltiles:
            # Log scheduling of scene ingestion.
            stile.scheduled = timezone.now()
            stile.write('Scheduled scene ingestion, waiting for worker availability.', SentinelTile.PENDING)
            ecs.process_l2a(stile.id)

        still_ingesting_tiles = True

    # Abort here and wait for callbacks from process_l2a and snap terrain correction.
    if still_ingesting_tiles:
        return

    # Flag to check composite tile status.
    composite_tiles_complete = not compositebuild.compositetiles.exclude(status=CompositeTile.FINISHED).exists()

    if not composite_tiles_complete:
        # Ensure compsitebuild status is "building tiles".
        if compositebuild.status != CompositeBuild.BUILDING_TILES:
            compositebuild.status = CompositeBuild.BUILDING_TILES
            compositebuild.save()

        # Call the composite tile builder for tiles that are unprocessed.
        compositetiles = compositebuild.compositetiles.filter(
            status__in=(CompositeTile.UNPROCESSED, CompositeTile.FAILED)
        )

        for compositetile in compositetiles:
            # Copy settings from compositebuild into each composite tile.
            if compositebuild.cloud_version:
                compositetile.cloud_version = compositebuild.cloud_version
            else:
                compositetile.cloud_classifier = compositebuild.cloud_classifier
            compositetile.include_sentinel_1 = compositebuild.include_sentinel_1
            compositetile.include_sentinel_2 = compositebuild.include_sentinel_2
            # Log scheduling of composite tile build.
            compositetile.scheduled = timezone.now()
            compositetile.write('Scheduled composite builder, waiting for worker availability.', CompositeTile.PENDING)
            # Call build task.
            ecs.process_compositetile(compositetile.id)
            # Break if composite builds have finished during the loop.
            if not compositebuild.compositetiles.exclude(status=CompositeTile.FINISHED).exists():
                compositebuild.status = CompositeBuild.FINISHED
                compositebuild.save()
                break
    else:
        # Composite build is complete, set status to "finished".
        compositebuild.status = CompositeBuild.FINISHED
        compositebuild.save()
        # Push report job.
        push_reports('composite', compositebuild.composite_id)


def process_sentinel_sns_message(event, context):
    """
    Ingest tile data based on notifications from SNS topic
    arn:aws:sns:eu-west-1:214830741341:NewSentinel2Product
    """
    message = json.loads(event['Records'][0]['Sns']['Message'])

    for tile in message['tiles']:
        # Get prefix for this tile.
        tile_prefix = tile['path']

        # Ensure prefix has trailing slash.
        if not tile_prefix.endswith('/'):
            tile_prefix += '/'

        # Skip this tile if it's already registered.
        if SentinelTile.objects.filter(prefix=tile_prefix).exists():
            continue

        # Create tile.
        stile = ingest_tile_from_prefix(tile_prefix)

        # Skip boundary geometries, they are spanning the world. TODO: fix geoms
        # on igestion instead of skipping them.
        if stile.prefix.startswith('tiles/1/') or stile.prefix.startswith('tiles/60/'):
            continue

        # Select filter geometry, either tile data geometry or tile geometry.
        filter_geom = stile.tile_data_geom if stile.tile_data_geom else stile.tile_geom
        if not filter_geom:
            continue

        # Find overlapping aggregation layers.
        qs = AggregationArea.objects.filter(
            geom__intersects=filter_geom,
        ).values_list(
            'aggregationlayer_id',
            flat=True,
        ).distinct()

        for aggregationlayer_id in qs:
            # Register tile with overlapping aggregationlayers.
            SentinelTileAggregationLayer.objects.get_or_create(
                sentineltile_id=stile.id,
                aggregationlayer_id=aggregationlayer_id,
            )

            # If requested, ingest scene now.
            ingestion_requested = CompositeBuildSchedule.objects.filter(
                active=True,
                continuous_scene_ingestion=True,
                compositebuilds__aggregationlayer_id=aggregationlayer_id,
            ).exists()
            if ingestion_requested:
                ecs.process_l2a(stile.id)


def clear_sentineltile(sentineltile_id):
    """
    Clear all tiles from this sentineltile and move it back to unprocessed.
    """
    # Get tile.
    tile = SentinelTile.objects.get(id=sentineltile_id)
    # Write process log and update status.
    tile.write('Clearing this sentineltile.', SentinelTile.PROCESSING)
    # Create S3 resource.
    s3 = boto3.resource('s3')
    # Get bucket if name is provided (this makes the clearing testable without
    # patching S3).
    if hasattr(settings, 'AWS_STORAGE_BUCKET_NAME_MEDIA'):
        bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME_MEDIA)
    else:
        bucket = None
    # Set delete batch size to boto3 delete_objects limit of 1000 objects.
    BATCH_SIZE = 1000
    # Loop through bands.
    for band in tile.sentineltileband_set.all():
        tile.write('Clearing band {}.'.format(band.band))
        # Delete all tiles for this band from S3.
        prefix = 'tiles/{}/'.format(band.layer_id)
        if bucket:
            bucket.objects.page_size(BATCH_SIZE).filter(Prefix=prefix).delete()
        # Unregister tiles from DB.
        qs = band.layer.rastertile_set.all()
        qs._raw_delete(qs.db)

    # Remove SCL if present.
    if hasattr(tile, 'sentineltilesceneclass'):
        tile.write('Clearing SCL.')
        # Delete all tiles for this band from S3.
        prefix = 'tiles/{}/'.format(tile.sentineltilesceneclass.layer_id)
        if bucket:
            bucket.objects.page_size(BATCH_SIZE).filter(Prefix=prefix).delete()
        # Unregister tiles from DB.
        qs = tile.sentineltilesceneclass.layer.rastertile_set.all()
        qs._raw_delete(qs.db)

    # Write success message, reset status.
    tile.write('Finished clearing tiles, resetting status to unprocessed.', SentinelTile.UNPROCESSED)


def clear_composite(composite_id):
    """
    Removes all tiles from this composite.
    """
    # Get composite.
    composite = Composite.objects.get(id=composite_id)
    # Create S3 resource.
    s3 = boto3.resource('s3')
    # Get bucket if name is provided (this makes the clearing testable without
    # patching S3).
    if hasattr(settings, 'AWS_STORAGE_BUCKET_NAME_MEDIA'):
        bucket = s3.Bucket(settings.AWS_STORAGE_BUCKET_NAME_MEDIA)
    else:
        bucket = None
    # Set delete batch size to boto3 delete_objects limit of 1000 objects.
    BATCH_SIZE = 1000
    # Loop through bands.
    for band in composite.compositeband_set.all():
        # Delete all tiles for this band from S3.
        prefix = 'tiles/{}/'.format(band.rasterlayer_id)
        if bucket:
            bucket.objects.page_size(BATCH_SIZE).filter(Prefix=prefix).delete()
        # Unregister tiles from DB.
        qs = band.rasterlayer.rastertile_set.all()
        qs._raw_delete(qs.db)
    # Remove composite tiles.
    composite.compositetile_set.all().delete()
    # Update all compositebuilds.
    for build in composite.compositebuild_set.all():
        build.write('Cleared composite.', CompositeBuild.CLEARED)


def push_scheduled_composite_builds():
    """
    Loop through the existing composite build schedules and run them
    asynchronously through ecs.
    """
    for schedule in CompositeBuildSchedule.objects.filter(active=True):

        # Skip if this is a weekly build schedule and it is not the right day
        # of the week.
        if schedule.interval == CompositeBuildSchedule.WEEKLY and datetime.datetime.now().weekday() != schedule.delay_build_days:
            schedule.write('Not the right day to run this weekly schedule.')
            continue

        # Skip if this is a monthly build schedule and it is not the right day
        # of the month.
        if schedule.interval == CompositeBuildSchedule.MONTHLY and datetime.datetime.now().day != (1 + schedule.delay_build_days):
            schedule.write('Not the right day to run this monthly schedule.')
            continue

        schedule.write('Pushing composite builds.')

        # Loop through the composite builds for this schedule and run them if
        # the date range is appropriate.
        for cbuild in schedule.compositebuilds.all():

            # Skip if the build is already in process.
            if cbuild.status in (CompositeBuild.PENDING, CompositeBuild.INGESTING_SCENES, CompositeBuild.BUILDING_TILES):
                continue

            # Skip if the composite build is pointing to the future.
            if cbuild.composite.min_date > datetime.datetime.now().date():
                continue

            # Skip if the composite build range is in the past minus the delay time.
            if (cbuild.composite.max_date + datetime.timedelta(days=schedule.delay_build_days)) < datetime.datetime.now().date():
                continue

            schedule.write('Pushing composite build {}'.format(cbuild.id))

            # Start composite build.
            cbuild.status = CompositeBuild.PENDING
            cbuild.save()
            ecs.composite_build_callback(cbuild.id, initiate=True, rebuild=True)
