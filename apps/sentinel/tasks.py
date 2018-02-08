from __future__ import unicode_literals

import glob
import io
import json
import logging
import os
import pathlib
import shutil
import time
import traceback
import uuid

import boto3
import botocore
import numpy
from botocore.client import Config
from celery import task
from celery.utils.log import get_task_logger
from dateutil import parser
from raster.models import RasterLayer, RasterLayerParseStatus, RasterTile
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.lookup import get_raster_tile
from raster.tiles.parser import RasterLayerParser
from raster.tiles.utils import tile_bounds, tile_index_range
from raster_aggregation.models import AggregationArea

from django.contrib.gis.gdal import Envelope, GDALRaster, OGRGeometry
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.files import File
from django.db.models import Count, F, Func
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
# from raster_api.views import get_tile
from sentinel import const
from sentinel.clouds.sun_angle import sun
from sentinel.clouds.tables import clouds
# from classify.clouds import clouds
from sentinel.models import (
    BucketParseLog, Composite, CompositeBuildLog, MGRSTile, SentinelTile, SentinelTileAggregationLayer,
    SentinelTileBand, ZoneOfInterest
)
from sentinel.utils import aggregate_tile, disaggregate_tile, get_composite_tile_indices, write_raster_tile

logger = get_task_logger(__name__)

boto3.set_stream_logger('boto3', logging.ERROR)


@task
def drive_sentinel_bucket_parser(max_keys=None):
    for utm_zone in range(1, const.NUMBER_OF_UTM_ZONES + 1):
        if BucketParseLog.objects.filter(utm_zone=utm_zone, end__isnull=True).exists():
            logger.info('UTM Zone {} is currently parsing, no new task scheduled.'.format(utm_zone))
        else:
            sync_sentinel_bucket_utm_zone.delay(utm_zone, max_keys=max_keys)


@task
def sync_sentinel_bucket_utm_zone(utm_zone, max_keys=None):
    """
    Synchronize the local database of sentinel scenes with the sentinel S3
    bucket.
    """
    # Create bucket parse log.
    log = BucketParseLog.objects.create(
        utm_zone=utm_zone,
        start=timezone.now()
    )
    log.write('Started parsing utm zone "{0}".'.format(utm_zone))

    # Initiate anonymous boto session.
    session = boto3.session.Session()
    config = Config(signature_version=botocore.UNSIGNED)
    client = session.client(const.CLIENT_TYPE, config=config)
    paginator = client.get_paginator(const.PAGINATOR_LOOKUP)
    prefix = const.PAGINATOR_BASE_PREFIX
    prefix += str(utm_zone) + '/'
    iterator = paginator.paginate(Bucket=const.BUCKET_NAME, Prefix=prefix)
    filtered_iterator = iterator.search(const.TILE_INFO_FILE_JMES_SEARCH)

    # Iteratively follow all keys.
    counter = 0
    for tileinfo_key in filtered_iterator:
        # Get prefix for this tile from tileinfo key.
        tile_prefix = tileinfo_key.split(const.TILE_INFO_FILE)[0]

        # Skip this tile if it's already registered.
        if SentinelTile.objects.filter(prefix=tile_prefix).exists():
            continue

        # Manual limiting of nr of objects.
        if max_keys is not None and counter >= max_keys:
            break
        counter += 1

        try:
            # Get tile info json data
            tileinfo = client.get_object(Key=tileinfo_key, Bucket=const.BUCKET_NAME)
            tileinfo = json.loads(tileinfo.get(const.TILEINFO_BODY_KEY).read().decode())

            # Get or create MGRS tile for this sentinel tile
            mgrs, created = MGRSTile.objects.get_or_create(
                grid_square=tileinfo['gridSquare'],
                utm_zone=tileinfo['utmZone'],
                latitude_band=tileinfo['latitudeBand'],
            )

            # For new MGRS tiles, set geometry from tile info
            if created:
                mgrs.geom = OGRGeometry(json.dumps(tileinfo['tileGeometry'])).geos
                mgrs.save()

            # Tile
            if 'tileGeometry' in tileinfo:
                tile_geom = OGRGeometry(str(tileinfo['tileGeometry'])).geos

                if not isinstance(tile_geom, Polygon):
                    tile_geom = Polygon(tile_geom, srid=tile_geom.srid)

                # Set geom to none if tile data geom is not valid.
                if not tile_geom.valid:
                    log.write('Found invalid geom for {0}. Valid Reason: {1}'.format(
                        tile_prefix,
                        tile_geom.valid_reason,
                    ))
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
                    log.write('Found invalid geom for {0}. Valid Reason: {1}'.format(
                        tile_prefix,
                        tile_data_geom.valid_reason,
                    ))
                    tile_data_geom = None
            else:
                tile_data_geom = None

            # Assume data coverage is zero if info is not available.
            data_coverage_percentage = tileinfo.get('dataCoveragePercentage', 0)

            # Compute sun angle at center of tile.
            cen = mgrs.geom.centroid.transform(4326, clone=True)
            date = parser.parse(tileinfo['timestamp'])
            alt, azim = sun(date.strftime('%y-%m-%d %H:%M:%S'), cen.y, cen.x)

            # Register tile, log error if creation failed.
            SentinelTile.objects.create(
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
            log.write('Registered ' + tile_prefix)
        except:
            log.write('Failed registering ' + tile_prefix + traceback.format_exc())

    # Log the end of the parsing process
    log.write('Finished parsing, {0} tiles created.'.format(counter))
    log.end = timezone.now()
    log.save()


@task
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
    )

    for tile in tiles:
        # Register tile for this aggregationarea.
        SentinelTileAggregationLayer.objects.get_or_create(
            sentineltile=tile,
            aggregationlayer_id=area.aggregationlayer_id,
        )
        # Ignore scenes that were already fetched.
        if tile.sentineltileband_set.count() > 0:
            continue


@receiver(post_save, sender=AggregationArea)
def trigger_scene_ingestion(sender, instance, **kwargs):
    get_aggregation_area_scenes.delay(instance.id)


@task
def drive_sentinel_queue(queue_limit=True, scene_limit=True):
    """
    Schedule download and parsing of sentinel scenes.
    """
    # List of parse status codes that indicate parsing is in process
    in_process_codes = (
        RasterLayerParseStatus.UNPARSED,
        RasterLayerParseStatus.DOWNLOADING_FILE,
        RasterLayerParseStatus.REPROJECTING_RASTER,
        RasterLayerParseStatus.CREATING_TILES,
        RasterLayerParseStatus.DROPPING_EMPTY_TILES,
    )

    # Count raster layers that are currently processing or waiting for
    # being processed.
    layers_processing = RasterLayer.objects.filter(
        parsestatus__status__in=in_process_codes
    ).count()

    # If number of layers is below a threshold, add more to queue
    if layers_processing >= const.MIN_TASK_QUEUE_LENGTH and queue_limit:
        msg = 'No new tasks pushed ({0} layers currently processing).'
        logger.info(msg.format(layers_processing))
        return

    composites = Composite.objects.filter(active=True)
    for composite in composites:
        # Get all active zones of interest for this composite.
        if composite.all_zones:
            zones = ZoneOfInterest.objects.filter(active=True)
        else:
            zones = composite.zonesofinterest.filter(active=True)
        # Loop through zones to add new scenes.
        for zone in zones.iterator():
            # Get MGRS tiles that intersect with the zone of interest, and do not
            # have more than two layers ingested. Currently exclude utm zones at
            # the time horizon, because geometries are wrapped around the composite.
            for mgrs in MGRSTile.objects.exclude(utm_zone__in=[1, 60]).filter(geom__intersects=zone.geom):
                # Count number of complete scenes for the given time frame and mgrs tile.
                nr_of_complete_scenes = mgrs.sentineltile_set.annotate(
                    band_count=Count('sentineltileband')
                ).filter(
                    band_count=const.NR_OF_BANDS,
                    collected__gte=composite.min_date,
                    collected__lte=composite.max_date,
                ).count()
                # Limit the number of scenes to a maximum.
                if nr_of_complete_scenes >= const.MAX_SCENES_PER_MGRSTILE and scene_limit:
                    continue
                # Get sentinel tiles that do not have bands yet.
                qs = SentinelTile.objects.filter(sentineltileband=None)
                # Limit to the MGRS tile.
                qs = qs.filter(mgrstile=mgrs)
                # Filter sentinel tiles by date.
                qs = qs.filter(
                    collected__gte=composite.min_date,
                    collected__lte=composite.max_date,
                )
                # Compute cohorts for cloud covers in steps of 10 percent, the cohorts
                # are necessary such that the date ordering still has an effect. The
                # goal is to find the newest tiles within the highest cloud cohort.
                qs = qs.annotate(
                    cloud_cohort=Func(F('cloudy_pixel_percentage') / 10, function='ROUND')
                )
                # Limit to cloud cover below a threshold.
                qs = qs.filter(cloud_cohort__lt=const.MAX_CLOUD_COHORT)
                # Only consider scenes with siginificant amounts of pixel values.
                qs = qs.filter(data_coverage_percentage__gt=const.MIN_PIXEL_COVERAGE)
                # Order by cloud cover cohort and newest first
                qs = qs.order_by('cloud_cohort', '-collected')
                # Get first tile matching the criteria
                tile = qs.distinct().first()
                if tile:
                    logger.info('Creating RasterLayers for SentinelTile {0}.'.format(tile.prefix))
                else:
                    logger.info('No more layers found to parse in zone {0}'.format(zone.name))
                    continue

                register_bands_for_tile(tile)


def register_bands_for_tile(tile):
    # Loop through all bands.
    for filename, description in const.BAND_CHOICES:

        # Continue if this band already exists.
        if SentinelTileBand.objects.filter(band=filename, tile=tile).exists():
            continue

        # Fix zoom level by band to ensure consistency.
        if filename in const.BANDS_10M:
            zoom = const.ZOOM_LEVEL_10M
        elif filename in const.BANDS_20M:
            zoom = const.ZOOM_LEVEL_20M
        else:
            zoom = const.ZOOM_LEVEL_60M

        # Create new raster layer and register it as sentinel band.
        layer = RasterLayer.objects.create(
            name=tile.prefix + filename,
            datatype=RasterLayer.CONTINUOUS,
            source_url=tile.get_source_url(filename),
            nodata=const.SENTINEL_NODATA_VALUE,
            max_zoom=zoom,
            build_pyramid=True,
            store_reprojected=False,
        )

        # Make sentinel bands available to all users.
        layer.publicrasterlayer.public = True
        layer.publicrasterlayer.save()

        # Register raster layer as sentinel tile band.
        try:
            SentinelTileBand.objects.create(
                layer=layer,
                band=filename,
                tile=tile,
            )
        except:
            layer.delete()
            raise


@task
def repair_incomplete_scenes():
    """
    Recreate missing sentinel tile bands on incomplete scenes.
    """
    qs = SentinelTile.objects.annotate(
        count=Count('sentineltileband')
    ).filter(
        count__gt=0,
        count__lt=const.NR_OF_BANDS,
    ).distinct()
    for incomplete in qs:
        register_bands_for_tile(incomplete)


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
        for band in bnds:
            try:
                tile = get_raster_tile(SentinelTileBand.objects.get(tile__prefix=sentineltile, band=band).layer_id, tilez, tilex, tiley)
            except SentinelTileBand.DoesNotExist:
                continue
            if not tile:
                continue
            # tile = get_tile(sentineltile + band, tilez, tilex, tiley)
            tiles.append((sentineltile, band, tile.rast.bands[0].data()))
    return tiles


def zone_tile_stacks(composite, tilex, tiley, tilez, level=const.LEVEL_L1C):
    """
    Iterator to provide scene level band stacks for all xyz tiles that
    intersect with a zone of interest.
    """
    logger.info('Creating Tiles for Layer "{0}" at {1}/{2}/{3}'.format(
        composite.name,
        tilez,
        tilex,
        tiley,
    ))

    sentineltiles = composite.get_sentineltiles()

    # Compute indexrange for this higher level tile.
    bounds = tile_bounds(tilex, tiley, tilez)
    indexrange = tile_index_range(bounds, const.ZOOM_LEVEL_60M, tolerance=1e-3)

    # Loop through tiles at 60m that intersect with bounding box.
    for tilex60 in range(indexrange[0], indexrange[2] + 1):
        for tiley60 in range(indexrange[1], indexrange[3] + 1):
            # Limit sentineltiles to those overlapping with the 60m tile.
            bounds60 = tile_bounds(tilex60, tiley60, const.ZOOM_LEVEL_60M)
            # Get tile bounding box as ewkt.
            bounds60 = 'SRID={0};{1}'.format(WEB_MERCATOR_SRID, Envelope(bounds60).wkt)
            # Filter sentinel scenes fthat overlap with this tile boundaries.
            sentineltiles60 = list(sentineltiles.filter(tile_data_geom__bboverlaps=bounds60).distinct().values_list('prefix', flat=True))

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

                            # Drop incomplete stacks.
                            for key, count in stacks_length.items():
                                if count != const.NR_OF_BANDS:
                                    del stacks[key]

                            # Skp if no complete stack is available for this tile.
                            if not len(stacks):
                                continue

                            # Return stacks as list the scene id is no longer
                            # relevant after this.
                            yield tilex10, tiley10, list(stacks.values())


@task
def drive_composite_builders(composite_ids=None):
    """
    Schedule composite creation based on zones of interest.
    """
    composites = Composite.objects.filter(active=True)
    if composite_ids:
        composites = composites.filter(id__in=composite_ids)

    for composite in composites:
        for tilex, tiley, tilez in get_composite_tile_indices(composite):
            # Check if the tile is currently building.
            processing = CompositeBuildLog.objects.filter(
                composite=composite,
                tilex=tilex,
                tiley=tiley,
                tilez=tilez,
                end__isnull=True,
            ).exists()

            if processing:
                continue

            # Register parse effort.
            wpp = CompositeBuildLog.objects.create(
                composite=composite,
                tilex=tilex,
                tiley=tiley,
                tilez=tilez,
                log='',
            )
            wpp.write('Scheduled composite builder, waiting for worker availability.')

            # Sleep to not put too many heavy tasks on the DB at once.
            time.sleep(1)

            build_composite(composite.id, tilex, tiley, tilez)

    return 'Started composites for layers {0}.'.format([composite.id for composite in composites])


@task
def build_composite(composite_id, tilex, tiley, tilez):
    """
    Build a cloud free unified base layer for a given zone of interest and for
    each sentinel band.

    If reset is activated, the files are deleted and re-created from scratch.
    """
    # Get compositeband and zone from db.
    composite = Composite.objects.get(id=composite_id)

    # Update composite parse process.
    wpp = CompositeBuildLog.objects.filter(
        composite=composite,
        tilex=tilex,
        tiley=tiley,
        tilez=tilez,
        end__isnull=True,
    ).first()

    wpp.start = timezone.now()
    wpp.write('Starting to build composite band.')

    # Get the list of master layers for all 13 bands.
    rasterlayer_lookup = composite.rasterlayer_lookup

    # Loop over all TMS tiles in a given zone and get band stacks for available
    # scenes in that tile.
    counter = 0
    for x, y, stacks in zone_tile_stacks(composite, tilex, tiley, tilez):
        # Compute the cloud probabilities for each avaiable scene band stack.
        cloud_probs = [clouds(stack) for stack in stacks]

        # Compute an array of scene indices with the lowest cloud probability.
        selector_index = numpy.argmin(cloud_probs, axis=0)

        # Create a copy of the generic results dict before updating values.
        result_dict = const.RESULT_DICT.copy()

        # Update result GDALRaster dictionary with bounds for this tile.
        bounds = tile_bounds(x, y, const.ZOOM_LEVEL_10M)
        result_dict['origin'] = bounds[0], bounds[3]

        # Loop over all bands.
        for key, name in const.BAND_CHOICES:
            # Merge scene tiles for this band into a composite tile using the selector index.
            bnds = numpy.array([stack[key] for stack in stacks])

            # Construct final composite band array from selector index.
            composite_data = bnds[selector_index, const.CLOUD_IDX1, const.CLOUD_IDX2]

            # Update results dict with data, using a random name for the in
            # memory raster.
            result_dict['bands'][0]['data'] = composite_data
            result_dict['name'] = '/vsimem/{}'.format(uuid.uuid4())

            # Convert gdalraster to file like object.
            dest = GDALRaster(result_dict)
            dest = io.BytesIO(dest.vsi_buffer)
            dest = File(dest, name='tile.tif')

            # Get current tile if it already exists.
            tile = RasterTile.objects.filter(
                rasterlayer_id=rasterlayer_lookup[key],
                tilex=x,
                tiley=y,
                tilez=const.ZOOM_LEVEL_10M,
            ).first()

            if tile:
                # Replace raster with updated composite.
                tile.rast = dest
                tile.save()
            else:
                # Register a new tile in database.
                RasterTile.objects.create(
                    rasterlayer_id=rasterlayer_lookup[key],
                    tilex=x,
                    tiley=y,
                    tilez=const.ZOOM_LEVEL_10M,
                    rast=dest,
                )

        # Log progress.
        counter += 1
        if counter % 100 == 0:
            logger.info('{count} World Tiles Created, currently at ({x}, {y}).'.format(count=counter, x=x, y=y))

    # Build pyramid for this zone.
    build_composite_pyramids(composite, tilex, tiley, tilez)

    return 'Successfully built compositeband {0} at (x={1}, y={2}, z={3})'.format(composite_id, tilex, tiley, tilez)


def build_composite_pyramids(composite, tilex, tiley, tilez):
    """
    Build pyramids for the global layer of each band.
    """
    # Get composite parse process logger.
    wpp = CompositeBuildLog.objects.filter(
        composite=composite,
        tilex=tilex,
        tiley=tiley,
        tilez=tilez,
        end__isnull=True,
    ).first()

    # Get rasterlayers.
    rasterlayer_lookup = composite.rasterlayer_lookup.values()

    bounds = tile_bounds(tilex, tiley, tilez)
    indexrange60 = tile_index_range(bounds, const.ZOOM_LEVEL_60M, tolerance=1e-3)

    # Loop over all zoom levels to construct pyramid.
    zoomrange = reversed(range(1, const.ZOOM_LEVEL_10M + 1))
    for zoom in zoomrange:
        # Compute index range for the zone of interest.
        factor = 2 ** (zoom - const.ZOOM_LEVEL_60M)
        indexrange = [int(idx * factor) for idx in indexrange60]
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

        logger.info(msg)
        wpp.write(msg)

        # Loop over composite band tiles in blocks of four.
        for tilex in range(indexrange[0], indexrange[2] + 1, 2):
            for tiley in range(indexrange[1], indexrange[3] + 1, 2):

                # Aggregate tiles for each composite band.
                for rasterlayer_id in rasterlayer_lookup:
                    result = []
                    none_found = True
                    # Aggregate each tile in the block of 2x2.
                    for idx, dat in enumerate(((0, 0), (1, 0), (0, 1), (1, 1))):
                        tile = RasterTile.objects.filter(
                            rasterlayer_id=rasterlayer_id,
                            tilez=zoom,
                            tilex=tilex + dat[0],
                            tiley=tiley + dat[1],
                        ).first()
                        if tile:
                            none_found = False
                            agg = aggregate_tile(tile.rast.bands[0].data())
                        else:
                            size = WEB_MERCATOR_TILESIZE // 2
                            agg = numpy.zeros((size, size), dtype=numpy.int16)
                        result.append(agg)

                    # Continue if no tile could be found for this 2x2 block.
                    if none_found:
                        continue

                    # Combine the aggregated version of the tiles to a new full tile at lower zoom level.
                    upper = numpy.append(result[0], result[1], axis=1)
                    lower = numpy.append(result[2], result[3], axis=1)
                    result = numpy.append(upper, lower, axis=0)

                    # Commit raster to DB.
                    write_raster_tile(rasterlayer_id, result, zoom - 1, tilex // 2, tiley // 2)

    wpp.end = timezone.now()
    wpp.write('Finished building pyramid.')


@task
def upgrade_sentineltile_to_l2a(sentineltile_id):
    tile = SentinelTile.objects.get(id=sentineltile_id)
    # Return if the product is already at Level 2.
    if tile.level == const.LEVEL_L2A:
        return

    # Abort if image is before L2A avaliablitiy cutoff.
    if tile.collected.date() < const.L2A_AVAILABILITY_DATE:
        return

    # Update level.
    tile.level = const.LEVEL_L2A
    tile.save()

    # Update raster layers with L2A bucket addresses, which triggers
    # re-parsing.
    for band in tile.sentineltileband_set.all():
        band.layer.source_url = tile.get_source_url(band.band)
        band.layer.save()


PRODUCT_DOWNLOAD_CMD_TMPL = 'java -jar /ProductDownload/ProductDownload.jar --sensor S2 --aws --out /rasterwd/products/{tile_id} --store AWS --limit 1 --tiles {mgrs_code} --start {start} --end {end}'
SEN2COR_CMD_TMPL = '/home/mrdjango/Sen2Cor-2.4.0-Linux64/bin/L2A_Process --resolution 10 {product_path}'


@task
def process_l2a(sentineltile_id, push_rasters=False):
    # Open sentinel tile instance.
    tile = SentinelTile.objects.get(id=sentineltile_id)

    # Construct download command.
    mgrs_code = '{0}{1}{2}'.format(
        tile.mgrstile.utm_zone,
        tile.mgrstile.latitude_band,
        tile.mgrstile.grid_square
    )
    productdownload_cmd = PRODUCT_DOWNLOAD_CMD_TMPL.format(
        tile_id=tile.id,
        mgrs_code=mgrs_code,
        start=tile.collected.date(),
        end=tile.collected.date(),
    )

    # Download the scene.
    os.system(productdownload_cmd)

    # Construct Sen2Cor command.
    product_path = glob.glob('/rasterwd/products/{}/*.SAFE'.format(tile.id))[0]
    sen2cor_cmd = SEN2COR_CMD_TMPL.format(product_path=product_path)

    # Apply atmoshperic correction.
    os.system(sen2cor_cmd)

    # Update level.
    if tile.level != const.LEVEL_L2A:
        tile.level = const.LEVEL_L2A
        tile.save()

    # Ingest the resulting rasters as tiles.
    for filename, description in const.BAND_CHOICES:

        # Fix zoom level by band to ensure consistency.
        if filename in const.BANDS_10M:
            resolution = '10'
            zoom = const.ZOOM_LEVEL_10M
        elif filename in const.BANDS_20M:
            resolution = '20'
            zoom = const.ZOOM_LEVEL_20M
        else:
            resolution = '60'
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

        # Get path of corrected image for this band, use uncorrected for 60m.
        if resolution == '60':
            glob_pattern = '/rasterwd/products/{tile_id}/S2*_MSIL1C*.SAFE/GRANULE/*/IMG_DATA/*{band}'.format(
                tile_id=tile.id,
                band=band.band,
            )
            bandpath = glob.glob(glob_pattern)
        else:
            glob_pattern = '/rasterwd/products/{tile_id}/S2*_MSIL2A*.SAFE/GRANULE/*/IMG_DATA/R{resolution}m/*{band}_{resolution}m.jp2'.format(
                tile_id=tile.id,
                band=band.band.split('.jp2')[0],
                resolution=resolution,
            )
            bandpath = glob.glob(glob_pattern)

        # Continue if file has not been created.
        if not len(bandpath):
            print('No source found for band ', band.band)
            continue
        else:
            print('Processing', band)
            bandpath = bandpath[0]

        # Create workdir for parsing.
        tmpdir = '/rasterwd/products/{tile_id}/tmp'.format(tile_id=tile.id)
        pathlib.Path(tmpdir).mkdir(parents=True, exist_ok=True)
        intermediate_rst = os.path.join(tmpdir, band.band.split('.jp2')[0] + '.tif')
        print('Intermediate raster is ', intermediate_rst)
        target_rst = os.path.join(tmpdir, 's2_' + '_'.join(tile.prefix.split('/')[1:]) + band.band.split('.jp2')[0] + '.tif')
        print('Target raster is ', target_rst)

        # Transform raster into cloud optimized geotiff in Web Mercator.
        os.system('gdalwarp -t_srs EPSG:{} {} {} -co TILED=YES -co BLOCKXSIZE=256 -co BLOCKYSIZE=256 -co COMPRESS=DEFLATE -co PREDICTOR=2'.format(
            WEB_MERCATOR_SRID,
            bandpath,
            intermediate_rst,
        ))

        os.system('gdaladdo -r average {} 2 4 6 8 16 32'.format(
            intermediate_rst,
        ))

        os.system('gdal_translate {} {} -co TILED=YES -co COPY_SRC_OVERVIEWS=YES -co COMPRESS=DEFLATE -co PREDICTOR=2'.format(
            intermediate_rst,
            target_rst,
        ))
        if push_rasters:
            push_and_parse_rasters(tmpdir, band, target_rst)
        else:
            locally_parse_raster(tmpdir, band, target_rst, zoom)

    # Remove main product files.
    shutil.rmtree('/rasterwd/products/{}'.format(tile.id))


def push_and_parse_rasters(tmpdir, band, target_rst):
    """
    Stores the raster bands as RasterLayer files. This triggers regular parsing.
    """
    # Store cloud optimized tif as source in raster model. This triggers
    # tiling automatically.
    band.layer.rasterfile = File(
        open(target_rst, 'rb'),
        name=os.path.basename(target_rst)
    )
    band.layer.source_url = ''
    band.layer.save()

    # Remove intermediate files.
    shutil.rmtree(tmpdir)


def locally_parse_raster(tmpdir, band, target_rst, zoom):
    """
    Instead of uploading the reprojected tif, we could parse the rasters right
    here. This would allow to never store the full tif files, but is more
    suceptible to random killing of spot instances.
    """
    # Open parser for the band, set tempdir and remove previous log.
    parser = RasterLayerParser(band.layer_id)
    parser.tmpdir = tmpdir
    parser.rasterlayer.parsestatus.log = ''
    parser.rasterlayer.parsestatus.save()

    # Open rasterlayer as GDALRaster, assign to parser attribute.
    parser.dataset = GDALRaster(target_rst)
    parser.extract_metadata()

    # Reproject and tile dataset.
    try:
        parser.create_tiles(list(range(zoom + 1)))
        parser.send_success_signal()
    except:
        print('Failed parsing', band.band, traceback.format_exc())
        parser.log(
            traceback.format_exc(),
            status=parser.rasterlayer.parsestatus.FAILED
        )
    finally:
        shutil.rmtree(parser.tmpdir)


def fargate_process_l2a(sentineltile_id):
    """
    Process Sentinel Tile L2A ingestion on Fargate.
    """
    client = boto3.client('ecs', region_name='us-east-1')
    return client.run_task(
        cluster='tesselo-workers',
        taskDefinition='tesselo-process-l2a-8GB-2vCPU:1',
        overrides={
            'containerOverrides': [
                {
                    'name': 'tesselo',
                    'command': [
                        'python3',
                        'manage.py',
                        'process_l2a',
                        str(stile.id),
                    ],
                },
            ],
        },
        launchType='FARGATE',
        networkConfiguration={
            'awsvpcConfiguration': {
                'subnets': [
                    'subnet-4ae19b65',
                    'subnet-5007051b',
                ],
                'securityGroups': [
                    'sg-66ef6c11',
                ],
                'assignPublicIp': 'ENABLED',
            }
        }
    )


def build_composite(aggregationlayer_id, composite_id):
    """
    Builds a composite over an aggregationlayer.
    """
    agglayer = AggregationLayer.objects.get(pk=aggregationlayer_id)
    composite = Composite.objects.get(pk=composite_id)
    sentineltiles = composite.get_sentineltiles()

    for stile in sentineltiles:
        if stile.level != const.LEVEL_L2A:
            fargate_process_l2a(stile.id)
