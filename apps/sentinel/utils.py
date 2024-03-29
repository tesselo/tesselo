import io
import shutil
import traceback
import uuid

import boto3
import numpy
import sentry_sdk
from django.conf import settings
from django.contrib.gis.gdal import GDALRaster, SpatialReference
from django.core.files.storage import default_storage
from raster.models import RasterLayerParseStatus
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE, WEB_MERCATOR_WORLDSIZE
from raster.tiles.parser import RasterLayerParser
from raster.tiles.utils import tile_bounds, tile_index_range, tile_scale
from rasterio import Affine
from rasterio.io import MemoryFile
from rasterio.warp import Resampling

from sentinel import const


def aggregate_tile(tile, target_dtype=None, discrete=False):
    """
    Use the gdal resampling algorithm to do aggregation of input numpy arrays.

    By default, bilinear resampling will be used. If the discrete flag is set,
    nearest neighbor resampling will be used.
    """
    resampling = Resampling.nearest if discrete else Resampling.bilinear
    # Create arbitrary affine. These values do not matter for a simple resampling
    # because resampling is the same anywhere in the world.
    transform = Affine(1, 0, 0, 0, -1, 0)
    # Prepare creation args for an in-memory tif file that we will use for resampling.
    creation_args = {
        'driver': 'GTiff',
        'dtype': tile.dtype,
        'nodata': None,
        'width': tile.shape[1],
        'height': tile.shape[0],
        'count': 1,
        'crs': f'EPSG:{WEB_MERCATOR_SRID}',
        'transform': transform,
    }
    # Open a new raster in memory.
    with MemoryFile() as memfile_src:
        with memfile_src.open(**creation_args) as src:
            # Write the tile data into the memory file.
            src.write(tile, 1)
            # Resample the tile data using the nearest neighbor mode from gdal.
            # This is done by reading the first band and resample into smaller shape.
            tile = src.read(
                1,
                out_shape=(
                    1,
                    int(creation_args['height'] / 2),
                    int(creation_args['width'] / 2),
                ),
                resampling=resampling,
            )

    # Convert to a specific type if requested.
    if target_dtype:
        tile = tile.astype(target_dtype)
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


def get_composite_tile_indices(composite, zoom=const.ZOOM_LEVEL_WORLDLAYER):
    """
    Get x-y-z tile indexes for all tiles intersecting over this compositeband's
    zones of interest.
    """
    # Create set to hold tile indexes.
    indexranges = set()
    # Loop through all composite tiles.
    for ctile in composite.compositetile_set.all():
        # Get index range from sentinel tile index.
        extent = tile_bounds(ctile.tilex, ctile.tiley, ctile.tilez)
        indexrange = tile_index_range(extent, zoom, tolerance=1e-3)
        # Add additional tiles to set.
        for tilex in range(indexrange[0], indexrange[2] + 1):
            for tiley in range(indexrange[1], indexrange[3] + 1):
                indexranges.add((tilex, tiley, zoom))

    for combo in indexranges:
        yield combo


def get_sentinel_tile_indices(sentineltile, zoom=const.ZOOM_LEVEL_10M):
    """
    Get x-y-z tile indexes for all tiles intersecting with this sentineltile's
    data geometry.
    """
    geom = sentineltile.tile_data_geom.transform(WEB_MERCATOR_SRID, clone=True)
    indexrange = tile_index_range(geom.extent, zoom, tolerance=1e-3)
    for tilex in range(indexrange[0], indexrange[2] + 1):
        for tiley in range(indexrange[1], indexrange[3] + 1):
            yield tilex, tiley, zoom


def get_raster_tile(layer_id, tilez, tilex, tiley, look_up=True):
    """
    Bypass the database to fetch files using structured file name scheme. If the
    requested tile does not exists, higher level tiles are searched. If a higher
    level tile is found, it is warped to the requested zoom level. This ensures
    that a tile can be requested at any zoom level.
    """
    # If asked for, add lower zoom levels as source candidates. Upper tiles are
    # then down-scaled to the higher zoom levels.
    if look_up:
        zoomrange = range(tilez, -1, -1)
    else:
        zoomrange = [tilez]

    # Loop through zoom levels to search for a tile
    for zoom in zoomrange:

        # Compute multiplier to find parent raster
        multiplier = 2 ** (tilez - zoom)

        # Get object from s3 if exists. Otherwise continue looking "upwards" to
        # find higher level tiles.
        filename = 'tiles/{}/{}/{}/{}.tif'.format(
            layer_id,
            zoom,
            int(tilex / multiplier),
            int(tiley / multiplier),
        )

        if hasattr(settings, 'AWS_STORAGE_BUCKET_NAME_MEDIA') and settings.AWS_STORAGE_BUCKET_NAME_MEDIA is not None:
            s3 = boto3.client('s3')
            try:
                tile = s3.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME_MEDIA, Key=filename)
            except s3.exceptions.NoSuchKey:
                continue
            tile = tile['Body']
        else:
            if default_storage.exists(filename):
                tile = default_storage.open(filename)
            else:
                continue

        # Convert tile data into a GDALRaster.
        try:
            tile = GDALRaster(tile.read())
        except Exception as e:
            sentry_sdk.capture_exception(e)
            continue

        # If the tile is a parent of the original, warp it to the
        # original request tile.
        if zoom < tilez:
            # Compute bounds and scale of the requested tile.
            bounds = tile_bounds(tilex, tiley, tilez)
            tilescale = tile_scale(tilez)

            # Warp parent tile to child tile in memory.
            tile = tile.warp({
                'driver': 'MEM',
                'width': WEB_MERCATOR_TILESIZE,
                'height': WEB_MERCATOR_TILESIZE,
                'scale': [tilescale, -tilescale],
                'origin': [bounds[0], bounds[3]],
            })

        return tile


def write_raster_tile(layer_id, result, tilez, tilex, tiley, nodata_value=const.SENTINEL_NODATA_VALUE, datatype=2, merge_with_existing=True, nr_of_bands=1):
    """
    Commit a rastertile into the DB and storage.
    """
    # Don't create nodata tiles.
    if numpy.all(result == nodata_value):
        return
    # Compute bounds and scale for the target tile.
    bounds = tile_bounds(tilex, tiley, tilez)
    scale = tile_scale(tilez)
    filename = 'tiles/{}/{}/{}/{}.tif'.format(layer_id, tilez, tilex, tiley)

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
        'papsz_options': {
            'compress': 'deflate',
            'predictor': 2,
        },
    }

    # Try getting tile from S3.
    if merge_with_existing:
        tile = get_raster_tile(layer_id, tilez, tilex, tiley)

        if tile:
            # Get current pixel array for this tile.
            current = tile.bands[0].data().astype(result.dtype)
            # Flatten the data if the input was flat.
            if result.shape[0] == 65536:
                current = current.ravel()
            # Add values from current array to result for pixels
            # where result is nodata. This ensures that areas
            # not covered by this zone stay present in the upper
            # pyramid levels, i.e. it unifies zone level pyramids.
            result_nodata = result == nodata_value
            result[result_nodata] = current[result_nodata]

    # Add result to target dictionary.
    if nr_of_bands > 1:
        for index in range(nr_of_bands):
            result_dict['bands'] = [{'nodata_value': None, 'data': result[index]} for index in range(nr_of_bands)]
    else:
        result_dict['bands'] = [{'nodata_value': nodata_value, 'data': result}]

    # Instanciate GDALRaster.
    dest = GDALRaster(result_dict)
    # Convert GDALRaster to file-like object.
    dest = io.BytesIO(dest.vsi_buffer)
    # Upload merged tile to s3.
    if hasattr(settings, 'AWS_STORAGE_BUCKET_NAME_MEDIA') and settings.AWS_STORAGE_BUCKET_NAME_MEDIA is not None:
        s3 = boto3.client('s3')
        s3.upload_fileobj(dest, settings.AWS_STORAGE_BUCKET_NAME_MEDIA, filename)
    else:
        default_storage.save(filename)


def populate_raster_metadata(raster):
    """
    For manually created rasters, set the extent to the entire world such that
    metadata parameters are populated. The metadata is used in multiple
    locations, especially for aggregation.
    """
    # Compute metadata parameters covering the world.
    nr_of_pixels = WEB_MERCATOR_TILESIZE * 2 ** const.ZOOM_LEVEL_10M
    raster.metadata.uperleftx = -WEB_MERCATOR_WORLDSIZE / 2
    raster.metadata.uperlefty = WEB_MERCATOR_WORLDSIZE / 4
    raster.metadata.width = nr_of_pixels
    raster.metadata.height = nr_of_pixels / 2
    raster.metadata.scalex = WEB_MERCATOR_WORLDSIZE / nr_of_pixels
    raster.metadata.scaley = -WEB_MERCATOR_WORLDSIZE / nr_of_pixels
    raster.metadata.skewx = 0
    raster.metadata.skewy = 0
    raster.metadata.numbands = 1
    raster.metadata.srs_wkt = SpatialReference(WEB_MERCATOR_SRID).wkt
    raster.metadata.srid = WEB_MERCATOR_SRID
    raster.metadata.max_zoom = const.ZOOM_LEVEL_10M
    raster.metadata.save()
    # Update parse status to parsed.
    raster.parsestatus.status = RasterLayerParseStatus.FINISHED
    raster.parsestatus.save()


def locally_parse_raster(tmpdir, rasterlayer_id, src_rst, zoom, remove_tmpdir=True, min_zoom=0, fallback_srid=None):
    """
    Instead of uploading the reprojected tif, we could parse the rasters right
    here. This would allow to never store the full tif files, but is more
    suceptible to random killing of spot instances.
    """
    # Open parser for the band, set tempdir and remove previous log.
    parser = RasterLayerParser(rasterlayer_id)
    parser.tmpdir = tmpdir
    parser.rasterlayer.parsestatus.log = ''
    parser.rasterlayer.parsestatus.save()

    # Open rasterlayer as GDALRaster, assign to parser attribute.
    parser.dataset = GDALRaster(src_rst, write=True)

    # Try to use the fallback SRID for the raster if it is unspecified.
    if parser.dataset.srs is None:
        parser.dataset.srid = fallback_srid
    parser.extract_metadata()

    # Reproject the rasterfile to web mercator.
    if parser.dataset.srid != WEB_MERCATOR_SRID:
        parser.reproject_rasterfile()

    # Clear current tiles.
    parser.drop_all_tiles()

    # Create tile pyramid.
    try:
        parser.create_tiles(list(reversed(range(min_zoom, zoom + 1))))
        parser.send_success_signal()
    except Exception as e:
        sentry_sdk.capture_exception(e)
        parser.log(
            traceback.format_exc(),
            status=parser.rasterlayer.parsestatus.FAILED
        )
        raise
    finally:
        shutil.rmtree(parser.tmpdir, ignore_errors=True)
