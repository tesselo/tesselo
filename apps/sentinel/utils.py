import io
import uuid

import numpy
from raster.models import RasterTile
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import tile_bounds, tile_index_range, tile_scale

from django.contrib.gis.gdal import GDALRaster
from django.core.files import File
from sentinel import const
from sentinel.models import ZoneOfInterest


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


def get_world_tile_indices(world):
    """
    Get x-y-z tile indexes for all tiles intersecting over this compositeband's
    zones of interest.
    """
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
                yield tilex, tiley, const.ZOOM_LEVEL_WORLDLAYER


def get_sentinel_tile_indices(sentineltile):
    """
    Get x-y-z tile indexes for all tiles intersecting with this sentineltile's
    data geometry.
    """
    geom = sentineltile.tile_data_geom.transform(WEB_MERCATOR_SRID, clone=True)
    indexrange = tile_index_range(geom.extent, const.ZOOM_LEVEL_10M, tolerance=1e-3)
    for tilex in range(indexrange[0], indexrange[2] + 1):
        for tiley in range(indexrange[1], indexrange[3] + 1):
            yield tilex, tiley, const.ZOOM_LEVEL_10M


def write_raster_tile(layer_id, result, tilez, tilex, tiley, nodata_value=const.SENTINEL_NODATA_VALUE, datatype=2):
    """
    Commit a rastertile into the DB and storage.
    """
    # Compute bounds and scale for the target tile.
    bounds = tile_bounds(tilex, tiley, tilez)
    scale = tile_scale(tilez)

    # Instantiate target GDALRaster dict.
    result_dict = {
        'name': '/vsimem/{}'.format(uuid.uuid4()),
        'driver': 'tif',
        'origin': (bounds[0], bounds[3]),
        'width': WEB_MERCATOR_TILESIZE,
        'height': WEB_MERCATOR_TILESIZE,
        'scale': [scale, -scale],
        'srid': WEB_MERCATOR_SRID,
        'datatype': datatype,
        'bands': [{'nodata_value': nodata_value, }],
        'papsz_options': {
            'compress': 'deflate',
            'predictor': 2,
        },
    }

    # Write tile to database, update if tile already exists.
    tile = RasterTile.objects.filter(
        rasterlayer_id=layer_id,
        tilez=tilez,
        tilex=tilex,
        tiley=tiley,
    ).first()

    if tile:
        try:
            # Get current array for this tile.
            current = tile.rast.bands[0].data()
            # Add values from current array to result for pixels
            # where result is nodata. This ensures that areas
            # not covered by this zone stay present in the upper
            # pyramid levels, i.e. it unifies zone level pyramids.
            result_nodata = result == nodata_value
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
            rasterlayer_id=layer_id,
            tilez=tilez,
            tilex=tilex,
            tiley=tiley,
            rast=dest,
        )
