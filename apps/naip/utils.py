from math import floor

import numpy
from raster.tiles.const import WEB_MERCATOR_SRID
from raster.tiles.utils import tile_bounds, tile_scale

from django.contrib.gis.gdal import OGRGeometry
from naip.models import NAIPQuadrangle

# Quadrangles are 8 x 8 Squares of a 1x1 Lat/Lon box. The NAIP tiles are
# quarters of the quadrangles.
QUADRANGLE_SIZE = 8.0
NAIP_QUADRANGLE_SIZE = QUADRANGLE_SIZE * 2.0


def get_quadrangles_from_coords(x, y):
    """
    Retieve a Queryset with all NAIP Quandrangles that intersect with the input
    coorinates.
    """
    # Get lat/lon integers.
    int_x = int(x)
    int_y = int(y)

    # Get lat/lon fractions (growing s->n and e->w).
    frac_x = 1 - abs(x) % 1
    frac_y = 1 - abs(y) % 1

    # Compute index for sub quad.
    sub_quad_x = int(floor(frac_x * QUADRANGLE_SIZE))
    sub_quad_y = int(floor(frac_y * QUADRANGLE_SIZE))
    sub_quad_idx = sub_quad_x + (QUADRANGLE_SIZE * sub_quad_y) + 1

    # Compute in which corner this coordinate sits.
    naip_sub_quad_x = 'w' if int(floor(frac_x * NAIP_QUADRANGLE_SIZE)) % 2 == 0 else 'e'
    naip_sub_quad_y = 'n' if int(floor(frac_y * NAIP_QUADRANGLE_SIZE)) % 2 == 0 else 's'
    corner = naip_sub_quad_y + naip_sub_quad_x

    return NAIPQuadrangle.objects.filter(
        lat=int_y,
        lon=int_x,
        subquad=sub_quad_idx,
        corner=corner,
    )


def get_naip_tile(tilez, tilex, tiley, source, year=None):
    """
    Construct a naip tile from tms indices.
    """
    from raster_api.views import get_tile
    # Get tile coords and bounds.
    bounds = tile_bounds(tilex, tiley, tilez)
    scale = tile_scale(int(tilez))
    # Transform bounds to lat lon.
    bbox = OGRGeometry.from_bbox(bounds)
    bbox.srid = WEB_MERCATOR_SRID
    bbox.transform(4326)
    bounds_wgs84 = bbox.extent
    # Prepare array with naip quad prefixes.
    quad_prefixes = []
    # Step through lat/lon quad bounds that intersect with this tile.
    step_x = bounds_wgs84[0]
    while step_x <= bounds_wgs84[2]:
        step_y = bounds_wgs84[1]
        while step_y <= bounds_wgs84[3]:
            # Get quadrangle for this step.
            if year:
                quad = get_quadrangles_from_coords(step_x, step_y).filter(source=source, date__year=year).first()
            else:
                quad = get_quadrangles_from_coords(step_x, step_y).filter(source=source).order_by('-date').first()
            # Add quadrangle to candidates list.
            if quad:
                quad_prefixes.append(quad.prefix)
            # Check if at last step.
            if step_y == bounds_wgs84[3]:
                break
            # Increase coodinates by one quadrangle width.
            step_y += 1 / NAIP_QUADRANGLE_SIZE
            # Ensure there is no overstepping of the max bounds.
            step_y = min(step_y, bounds_wgs84[3])
            print(step_x, step_y)
        # Check if at last step.
        if step_x == bounds_wgs84[2]:
            break
        # Increase coodinates by one quadrangle width.
        step_x += 1 / NAIP_QUADRANGLE_SIZE
        # Ensure there is no overstepping of the max bounds.
        step_x = min(abs(step_x), abs(bounds_wgs84[2]))

    # Return empty if not prefixes were found.
    if not len(quad_prefixes):
        return

    # Prepare image data arrays.
    red = numpy.zeros((256, 256), 'uint8')
    green = numpy.zeros((256, 256), 'uint8')
    blue = numpy.zeros((256, 256), 'uint8')
    if source == NAIPQuadrangle.RGBIR:
        ir = numpy.zeros((256, 256), 'uint8')

    # The quad lookup might include some quads at the boundary twice at the
    # moment. Make them unique by using set.
    for prefix in set(quad_prefixes):
        # Compute tile bounds and scale.
        dtype, tile_data = get_tile('aws-naip/{}'.format(prefix), bounds, scale)
        red[red == 0] = tile_data[0]['data'][red == 0]
        green[green == 0] = tile_data[1]['data'][green == 0]
        blue[blue == 0] = tile_data[2]['data'][blue == 0]
        # If IR band is present, add that one too.
        if source == NAIPQuadrangle.RGBIR:
            ir[ir == 0] = tile_data[3]['data'][ir == 0]

    result = [{'data': red, 'nodata_value': None}, {'data': green, 'nodata_value': None}, {'data': blue, 'nodata_value': None}]
    if source == NAIPQuadrangle.RGBIR:
        result.append({'data': ir, 'nodata_value': None})

    return [
        (dtype, result)
    ]
