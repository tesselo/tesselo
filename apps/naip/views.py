from math import ceil, floor

from raster.tiles.const import WEB_MERCATOR_SRID
from raster.tiles.utils import tile_bounds

from django.contrib.gis.gdal import OGRGeometry
from naip.models import NAIPQuadrangle

# Quadrangles are 8 x 8 Squares of a 1x1 Lat/Lon box. The NAIP tiles are
# quarters of the quadrangles.
QUADRANGLE_INCREMENTS = [i / 8.0 for i in range(8)]
NAIP_TILE_INCREMENTS = [i / (8.0 * 2) for i in range(8 * 2)]
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
    sub_quad_idx = sub_quad_x + (4 * sub_quad_y) + 1

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


def get_naip_tile():
    """
    Construct a view that constructs a naip tile from tms indices.
    """
    # Transform bounds to lat lon.
    # bounds = tile_bounds(2122, 3338, 13)
    # bbox = OGRGeometry.from_bbox(bounds)
    # bbox.srid = WEB_MERCATOR_SRID
    # bbox.transform(4326)
    # bounds = bbox.extent
    # x = bounds[0]
    # y = bounds[1]
    lowest_quadrangle = min(QUADRANGLE_INCREMENTS, key=lambda x:abs(x - ximinmyNumber))

    # Find the lowest 1/16th quadrangle coordinates in x and y that intersects with
    # this tile.
    lowest_x = floor(bounds[0]) + int(floor(bounds[0] % 1 * QADRANGLE_SIZE))
    lowest_y = int(floor(bounds[1] % 1 * QADRANGLE_SIZE))
    highest_x = int(floor(bounds[2] % 1 * QADRANGLE_SIZE))
    highest_y = int(floor(bounds[3] % 1 * QADRANGLE_SIZE))

    # Get min and max lat/lon integers.
    xmin = abs(int(bounds[0]))
    xmax = abs(int(bounds[2]))
    ymin = int(bounds[1])
    ymax = int(bounds[3])

    quadrangles = []

    # Loop throug all integer lat/lon quadrangles.
    for x in range(xmin, xmax + 1):
        for y in range(ymin, ymax + 1):

            quadrangles.append(
                '{x}{y}'.format(x=x, y=y)
            )

    int(min(bounds[0], bounds_latlon[1]))
    int(max(bounds[0], bounds_latlon[1]))
