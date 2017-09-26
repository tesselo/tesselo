from __future__ import unicode_literals

import io
import json
import logging
import time
import traceback
import uuid

import botocore
import numpy
from botocore.client import Config
from celery import task
from celery.utils.log import get_task_logger
from dateutil import parser
from raster.models import RasterLayer, RasterLayerParseStatus, RasterTile
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import tile_bounds, tile_index_range, tile_scale

import boto3
from django.contrib.gis.gdal import Envelope, GDALRaster, OGRGeometry
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.files import File
from django.db.models import Count, F, Func
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from raster_aggregation.models import AggregationArea
from sentinel import const
from sentinel.clouds.sun_angle import sun
from sentinel.clouds.tables import clouds
# from classify.clouds import clouds
from sentinel.models import (
    BucketParseLog, MGRSTile, SentinelTile, SentinelTileAggregationLayer, SentinelTileBand, WorldLayerGroup,
    WorldParseProcess, ZoneOfInterest
)

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
        # Loop through all choices
        for filename, description in const.BAND_CHOICES:
            # Fix zoom level by band to ensure consistency.
            if filename in const.BANDS_10M:
                zoom = const.ZOOM_LEVEL_10M
            elif filename in const.BANDS_20M:
                zoom = const.ZOOM_LEVEL_20M
            else:
                zoom = const.ZOOM_LEVEL_60M
            # Create new raster layer and register it as sentinel band
            layer = RasterLayer.objects.create(
                name=tile.prefix + filename,
                datatype=RasterLayer.CONTINUOUS,
                source_url=tile.url + filename,
                nodata=const.SENTINEL_NODATA_VALUE,
                max_zoom=zoom,
                build_pyramid=True,
                store_reprojected=False,
            )
            try:
                SentinelTileBand.objects.create(
                    layer=layer,
                    band=filename,
                    tile=tile,
                )
            except:
                layer.delete()
                raise


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
    ).exclude(
        name__icontains='Big Kahuna'
    ).count()

    # If number of layers is below a threshold, add more to queue
    if layers_processing >= const.MIN_TASK_QUEUE_LENGTH and queue_limit:
        msg = 'No new tasks pushed ({0} layers currently processing).'
        logger.info(msg.format(layers_processing))
        return

    worlds = WorldLayerGroup.objects.filter(active=True)
    for world in worlds:
        # Get all active zones of interest for this world layer.
        if world.all_zones:
            zones = ZoneOfInterest.objects.filter(active=True)
        else:
            zones = world.zonesofinterest.filter(active=True)
        # Loop through zones to add new scenes.
        for zone in zones.iterator():
            # Get MGRS tiles that intersect with the zone of interest, and do not
            # have more than two layers ingested. Currently exclude utm zones at
            # the time horizon, because geometries are wrapped around the world.
            for mgrs in MGRSTile.objects.exclude(utm_zone__in=[1, 60]).filter(geom__intersects=zone.geom):
                # Count number of complete scenes for the given time frame and mgrs tile.
                nr_of_complete_scenes = mgrs.sentineltile_set.annotate(
                    band_count=Count('sentineltileband')
                ).filter(
                    band_count=const.NR_OF_BANDS,
                    collected__gte=world.min_date,
                    collected__lte=world.max_date,
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
                    collected__gte=world.min_date,
                    collected__lte=world.max_date,
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

                # Loop through all choices
                for filename, description in const.BAND_CHOICES:
                    # Fix zoom level by band to ensure consistency.
                    if filename in const.BANDS_10M:
                        zoom = const.ZOOM_LEVEL_10M
                    elif filename in const.BANDS_20M:
                        zoom = const.ZOOM_LEVEL_20M
                    else:
                        zoom = const.ZOOM_LEVEL_60M
                    # Create new raster layer and register it as sentinel band
                    layer = RasterLayer.objects.create(
                        name=tile.prefix + filename,
                        datatype=RasterLayer.CONTINUOUS,
                        source_url=tile.url + filename,
                        nodata=const.SENTINEL_NODATA_VALUE,
                        max_zoom=zoom,
                        build_pyramid=False,
                        store_reprojected=False,
                    )
                    SentinelTileBand.objects.create(
                        layer=layer,
                        band=filename,
                        tile=tile,
                    )


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
        for filename, description in const.BAND_CHOICES:
            # Contineu if this band already exists.
            if SentinelTileBand.objects.filter(band=filename, tile=incomplete).exists():
                continue
            # Fix zoom level by band to ensure consistency.
            if filename in const.BANDS_10M:
                zoom = const.ZOOM_LEVEL_10M
            elif filename in const.BANDS_20M:
                zoom = const.ZOOM_LEVEL_20M
            else:
                zoom = const.ZOOM_LEVEL_60M
            layer = RasterLayer.objects.create(
                name=incomplete.prefix + filename,
                datatype=RasterLayer.CONTINUOUS,
                source_url=incomplete.url + filename,
                nodata=const.SENTINEL_NODATA_VALUE,
                max_zoom=zoom,
                build_pyramid=False,
                store_reprojected=False,
            )
            SentinelTileBand.objects.create(
                layer=layer,
                band=filename,
                tile=incomplete,
            )


def get_range_tiles(sentineltiles, tilex, tiley, tilez):
    """
    Return a RasterTile queryset of tiles for the given indices.
    """
    bounds = tile_bounds(tilex, tiley, tilez)
    # Get tile bounding box as ewkt.
    bounds = 'SRID={0};{1}'.format(WEB_MERCATOR_SRID, Envelope(bounds).wkt)
    # Get mgrs tiles that overlap with this tile boundaries.
    mgrs = MGRSTile.objects.filter(
        geom__bboverlaps=bounds,
    ).exclude(
        utm_zone__in=[1, 60],
    ).values_list('id', flat=True)
    # Filter sentinel scenes for this tile, ordered by cloud cover and limited to a maximum number.
    data = sentineltiles.filter(mgrstile_id__in=mgrs).distinct()
    # Return data as tuples of scene, band number and pixel values.
    tiles = []
    for sentineltile in data.iterator():
        for band in sentineltile.sentineltileband_set.all():
            tile = RasterTile.objects.filter(rasterlayer_id=band.layer_id, tilez=tilez, tilex=tilex, tiley=tiley).first()
            if tile:
                tiles.append((sentineltile.id, band.band, tile.rast.bands[0].data()))
    return tiles


def zone_tile_stacks(world, tilex, tiley, tilez):
    """
    Iterator to provide scene level band stacks for all xyz tiles that
    intersect with a zone of interest.
    """
    logger.info('Creating Tiles for Layer "{0}" at {1}/{2}/{3}'.format(
        world.name,
        tilez,
        tilex,
        tiley,
    ))

    # Preload tiles that are populated on the bands based on the world
    # layer group settings.
    sentineltiles = SentinelTile.objects.exclude(
        sentineltileband=None,
    ).filter(
        collected__gte=world.min_date,
        collected__lte=world.max_date,
    ).order_by(
        'cloudy_pixel_percentage',
    )

    # Compute indexrange for this higher level tile.
    bounds = tile_bounds(tilex, tiley, tilez)
    indexrange = tile_index_range(bounds, const.ZOOM_LEVEL_60M, tolerance=1e-3)

    # Loop through tiles at 60m that intersect with bounding box.
    for tilex60 in range(indexrange[0], indexrange[2] + 1):
        for tiley60 in range(indexrange[1], indexrange[3] + 1):
            tiles60 = get_range_tiles(sentineltiles, tilex60, tiley60, const.ZOOM_LEVEL_60M)
            if not len(tiles60):
                continue

            # Loop through children tiles at 20m.
            for tilex20 in range(tilex60 * const.M26, (tilex60 + 1) * const.M26):
                for tiley20 in range(tiley60 * const.M26, (tiley60 + 1) * const.M26):

                    tiles20 = get_range_tiles(sentineltiles, tilex20, tiley20, const.ZOOM_LEVEL_20M)
                    if not len(tiles20):
                        continue

                    # Loop through children tiles at 10m.
                    for tilex10 in range(tilex20 * const.M12, (tilex20 + 1) * const.M12):
                        for tiley10 in range(tiley20 * const.M12, (tiley20 + 1) * const.M12):

                            tiles10 = get_range_tiles(sentineltiles, tilex10, tiley10, const.ZOOM_LEVEL_10M)
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
def drive_world_layers(world_ids=None):
    """
    Schedule world layer creation based on zones of interest.
    """
    worlds = WorldLayerGroup.objects.filter(active=True)
    if world_ids:
        worlds = worlds.filter(id__in=world_ids)

    for world in worlds:
        # Get all active zones of interest for this world layer.
        if world.all_zones:
            zones = ZoneOfInterest.objects.filter(active=True)
        else:
            zones = world.zonesofinterest.filter(active=True)

        # Build world layer tiles for each zone.
        for zone in zones:
            # Compute index range for this zone of interest.
            indexrange = zone.index_range(const.ZOOM_LEVEL_WORLDLAYER)

            for tilex in range(indexrange[0], indexrange[2] + 1):
                for tiley in range(indexrange[1], indexrange[3] + 1):

                    # Check if the zone is currently building.
                    processing = WorldParseProcess.objects.filter(
                        worldlayergroup=world,
                        tilex=tilex,
                        tiley=tiley,
                        tilez=const.ZOOM_LEVEL_WORLDLAYER,
                        end__isnull=True,
                    ).exists()

                    if processing:
                        continue

                    # Register parse effort.
                    WorldParseProcess.objects.create(
                        worldlayergroup=world,
                        tilex=tilex,
                        tiley=tiley,
                        tilez=const.ZOOM_LEVEL_WORLDLAYER,
                    )

                    # Sleep to not put too many heavy tasks on the DB at once.
                    time.sleep(1)

                    build_world_layers.delay(world.id, tilex, tiley, const.ZOOM_LEVEL_WORLDLAYER)

    return 'Started world layers for layers {0}.'.format([world.pk for world in worlds])


@task
def build_world_layers(world_id, tilex, tiley, tilez):
    """
    Build a cloud free unified base layer for a given zone of interest and for
    each sentinel band.

    If reset is activated, the files are deleted and re-created from scratch.
    """
    # Get worldlayer and zone from db.
    world = WorldLayerGroup.objects.get(id=world_id)

    # Update world parse process.
    WorldParseProcess.objects.filter(
        worldlayergroup=world,
        tilex=tilex,
        tiley=tiley,
        tilez=tilez,
        end__isnull=True,
    ).update(
        start=timezone.now()
    )

    # Get the list of master layers for all 13 bands.
    kahunas = world.kahunas

    # Loop over all TMS tiles in a given zone and get band stacks for available
    # scenes in that tile.
    counter = 0
    for x, y, stacks in zone_tile_stacks(world, tilex, tiley, tilez):
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
            # Merge scene tiles for this band into a world tile using the selector index.
            bnds = numpy.array([stack[key] for stack in stacks])

            # Construct final composite band array from selector index.
            composite = bnds[selector_index, const.CLOUD_IDX1, const.CLOUD_IDX2]

            # Update results dict with data, using a random name for the in
            # memory raster.
            result_dict['bands'][0]['data'] = composite
            result_dict['name'] = '/vsimem/{}'.format(uuid.uuid4())

            # Convert gdalraster to file like object.
            dest = GDALRaster(result_dict)
            dest = io.BytesIO(dest.vsi_buffer)
            dest = File(dest, name='tile.tif')

            # Get current tile if it already exists.
            tile = RasterTile.objects.filter(
                rasterlayer_id=kahunas[key],
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
                    rasterlayer_id=kahunas[key],
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
    build_world_pyramids(world, tilex, tiley, tilez)

    return 'Successfully built worldlayer {0} at (x={1}, y={2}, z={3})'.format(world_id, tilex, tiley, tilez)


def build_world_pyramids(world, tilex, tiley, tilez):
    """
    Build pyramids for the global layer of each band.
    """
    kahunas = world.kahunas.values()

    # Get index range at 60m.
    tilex_in = tilex
    tiley_in = tiley
    tilez_in = tilez

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

        logger.info('Creating World Pyramid at Zoom {0} for Index Range {1}.'.format(
            zoom - 1,
            [idx // 2 for idx in indexrange],
        ))

        # Loop over kahuna tiles in blocks of four.
        for tilex in range(indexrange[0], indexrange[2] + 1, 2):
            for tiley in range(indexrange[1], indexrange[3] + 1, 2):

                # Aggregate tiles for each kahuna band.
                for kahuna in kahunas:
                    result = []
                    none_found = True
                    # Aggregate each tile in the block of 2x2.
                    for idx, dat in enumerate(((0, 0), (1, 0), (0, 1), (1, 1))):
                        tile = RasterTile.objects.filter(
                            rasterlayer_id=kahuna,
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

                    # Compute bounds and scale for the target tile.
                    bounds = tile_bounds(tilex // 2, tiley // 2, zoom - 1)
                    scale = tile_scale(zoom - 1)

                    # Instantiate target GDALRaster dict.
                    result_dict = {
                        'name': '/vsimem/{}'.format(uuid.uuid4()),
                        'driver': 'tif',
                        'origin': (bounds[0], bounds[3]),
                        'width': WEB_MERCATOR_TILESIZE,
                        'height': WEB_MERCATOR_TILESIZE,
                        'scale': [scale, -scale],
                        'srid': WEB_MERCATOR_SRID,
                        'datatype': 2,
                        'bands': [{'nodata_value': 0, }],
                        'papsz_options': {
                            'compress': 'deflate',
                            'predictor': 2,
                        },
                    }

                    # Write tile to database, update if tile already exists.
                    tile = RasterTile.objects.filter(
                        rasterlayer_id=kahuna,
                        tilez=zoom - 1,
                        tilex=tilex // 2,
                        tiley=tiley // 2,
                    ).first()

                    if tile:
                        try:
                            # Get current array for this tile.
                            current = tile.rast.bands[0].data()
                            # Add values from current array to result for pixels
                            # where result is nodata. This ensures that areas
                            # not covered by this zone stay present in the upper
                            # pyramid levels, i.e. it unifies zone level pyramids.
                            result_nodata = result == const.SENTINEL_NODATA_VALUE
                            result[result_nodata] = current[result_nodata]
                        except:
                            # Different storage backends might raise different errors. So
                            # this has to be a catch-all.
                            pass

                        # Store result in raster.
                        result_dict['bands'][0]['data'] = result

                        # Convert gdalraster to file like object, and set
                        # the file object.
                        dest = GDALRaster(result_dict)
                        dest = io.BytesIO(dest.vsi_buffer)
                        dest = File(dest, name='tile.tif')
                        tile.rast = dest

                        # Write the tile update to db and storage.
                        tile.save()
                    else:
                        # Add result to GDALRaster dictionary.
                        result_dict['bands'][0]['data'] = result

                        # Convert gdalraster to file like object.
                        dest = GDALRaster(result_dict)
                        dest = io.BytesIO(dest.vsi_buffer)
                        dest = File(dest, name='tile.tif')

                        # Create a new tile if the world tile does not exist yet.
                        RasterTile.objects.create(
                            rasterlayer_id=kahuna,
                            tilez=zoom - 1,
                            tilex=tilex // 2,
                            tiley=tiley // 2,
                            rast=dest,
                        )

    # Update world parse process.
    WorldParseProcess.objects.filter(
        worldlayergroup=world,
        tilex=tilex_in,
        tiley=tiley_in,
        tilez=tilez_in,
        end__isnull=True,
    ).update(
        end=timezone.now()
    )


def aggregate_tile(tile):
    """
    Aggregate a tile array to the next zoom level using movin average. Create
    a 1-D array of half the size of the input data.

    Inspired by:
    https://stackoverflow.com/questions/16856788/slice-2d-array-into-smaller-2d-arrays
    """
    tile.shape = (const.AGG_TILE_SIZE, const.AGG_FACTOR, const.AGG_TILE_SIZE, const.AGG_FACTOR)
    tile = tile.swapaxes(1, 2)
    tile = tile.reshape(const.AGG_TILE_SIZE_SQ, const.AGG_FACTOR, const.AGG_FACTOR)
    tile = numpy.mean(tile, axis=(1, 2), dtype=numpy.int16)
    tile.shape = (const.AGG_TILE_SIZE, const.AGG_TILE_SIZE)
    return tile


def disaggregate_tile(tile, factor, offsetx, offsety):
    """
    Expand the tile array to a higher zoom level.
    """
    # Reshape data into a matrix.
    tile = tile.reshape(WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE)
    # Compute size of data block to be extracted.
    size = WEB_MERCATOR_TILESIZE // factor
    # Get data block for this offset. The numpy indexing order is (y, x).
    data = tile[int(offsety):int(offsety + size), int(offsetx):int(offsetx + size)]
    # Expand data repeating values by the factor to get back to the original size.
    return data.repeat(factor, axis=0).repeat(factor, axis=1)
