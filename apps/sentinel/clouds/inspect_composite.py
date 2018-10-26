import numpy
from PIL import Image
from raster.tiles.utils import tile_bounds

from django.contrib.gis.gdal import Envelope
from sentinel.models import CompositeTile, SentinelTileBand, SentinelTileSceneClass
from sentinel.utils import get_raster_tile

WEB_MERCATOR_SRID = 3857
ZOOM = 10
PAD = 5
SIZE = 266
SCENE_CLASS_COLORS = (
    (0, 250, 0),   # NO_DATA
    (250, 0, 0),   # SATURATED_OR_DEFECTIVE
    (50, 50, 150),   # DARK_AREA_PIXELS
    (20, 20, 20),   # CLOUD_SHADOWS
    (122, 239, 54),   # VEGETATION
    (189, 194, 0),   # NOT_VEGETATED
    (112, 96, 222),   # WATER
    (197, 11, 154),   # UNCLASSIFIED
    (250, 250, 250),   # CLOUD_MEDIUM_PROBABILITY
    (200, 200, 200),   # CLOUD_HIGH_PROBABILITY
    (100, 100, 100),   # THIN_CIRRUS
    (224, 152, 152),   # SNOW
)
R = [x[0] for x in SCENE_CLASS_COLORS]
G = [x[1] for x in SCENE_CLASS_COLORS]
B = [x[2] for x in SCENE_CLASS_COLORS]


def get_composite_tile(composite_id, tilez, tilex, tiley):
    """
    Identify which composite tile is relevant for this inpection.
    """
    if tilez < 10:
        raise ValueError('Zoom level needs to be 10 or higher.')

    # Compute multiplier to find parent raster
    multiplier = 2 ** (tilez - ZOOM)

    tilex_10 = int(tilex / multiplier)
    tiley_10 = int(tiley / multiplier)

    # Get object from s3 if exists. Otherwise continue looking "upwards" to
    # find higher level tiles.
    return CompositeTile.objects.get(
        composite=composite_id,
        tilez=ZOOM,
        tilex=tilex_10,
        tiley=tiley_10,
    )


def imagize(r, g, b):
    """
    Get RGB image channels from RGB GDALRaster tiles.
    """
    r = r.bands[0].data()
    g = g.bands[0].data()
    b = b.bands[0].data()

    clipper = 3e3

    r = numpy.clip(r, 0, clipper) * 255 / clipper
    g = numpy.clip(g, 0, clipper) * 255 / clipper
    b = numpy.clip(b, 0, clipper) * 255 / clipper

    r = numpy.pad(r, ((PAD, PAD), (PAD, PAD)), 'constant', constant_values=((255, 255), (255, 255))).astype('uint8')
    g = numpy.pad(g, ((PAD, PAD), (PAD, PAD)), 'constant', constant_values=((255, 255), (255, 255))).astype('uint8')
    b = numpy.pad(b, ((PAD, PAD), (PAD, PAD)), 'constant', constant_values=((255, 255), (255, 255))).astype('uint8')

    return r, g, b


def colorize(s):
    """
    Convert the scene class to RGB arrays using color scheme. This is used to
    get the corresponding SentinelTile list.
    """
    s = s.bands[0].data()
    # Use SCL layer to select pixel ranks.
    r = numpy.choose(s, R)
    g = numpy.choose(s, G)
    b = numpy.choose(s, B)
    # Pad all arrays for visual separation in final image.
    r = numpy.pad(r, ((PAD, PAD), (PAD, PAD)), 'constant', constant_values=((255, 255), (255, 255))).astype('uint8')
    g = numpy.pad(g, ((PAD, PAD), (PAD, PAD)), 'constant', constant_values=((255, 255), (255, 255))).astype('uint8')
    b = numpy.pad(b, ((PAD, PAD), (PAD, PAD)), 'constant', constant_values=((255, 255), (255, 255))).astype('uint8')

    return r, g, b


def get_tiles(sentineltiles, tilez, tilex, tiley):
    """
    Download tiles as GDALRaster tiles.
    """
    # Get raw image arrays.
    raw = []
    for stile in sentineltiles.order_by('collected'):
        try:
            r = stile.sentineltileband_set.get(band='B04.jp2').layer_id
            g = stile.sentineltileband_set.get(band='B03.jp2').layer_id
            b = stile.sentineltileband_set.get(band='B02.jp2').layer_id
            s = stile.sentineltilesceneclass.layer_id
        except (SentinelTileBand.DoesNotExist, SentinelTileSceneClass.DoesNotExist):
            raise

        r = get_raster_tile(r, tilez, tilex, tiley)
        g = get_raster_tile(g, tilez, tilex, tiley)
        b = get_raster_tile(b, tilez, tilex, tiley)
        s = get_raster_tile(s, tilez, tilex, tiley)

        raw.append([r, g, b, s])

    return raw


def construct_image_from_tiles(raw):
    """
    Construct the RGB images for visual spectrum and the sceneclass layers, and
    paste them together in one image with padding between the tiles.
    """
    # Pre-define variables.
    tr = tg = tb = trs = tgs = tbs = None
    # Populate variables.
    for r, g, b, s in raw:

        r, g, b = imagize(r, g, b)

        rs, gs, bs = colorize(s)

        if tr is not None:
            tr = numpy.hstack((tr, r))
            tg = numpy.hstack((tg, g))
            tb = numpy.hstack((tb, b))

            trs = numpy.hstack((trs, rs))
            tgs = numpy.hstack((tgs, gs))
            tbs = numpy.hstack((tbs, bs))
        else:
            tr = r
            tg = g
            tb = b

            trs = rs
            tgs = gs
            tbs = bs
    # Reshape arrays to image.
    target = numpy.array((tr.T, tg.T, tb.T))
    target_s = numpy.array((trs.T, tgs.T, tbs.T))
    target_final = numpy.array(list(numpy.hstack((target[i], target_s[i])) for i in range(3)))
    # Create and return image from array.
    return Image.fromarray(target_final.T)


def inspect_composite(composite_id, tilez, tilex, tiley):
    # Compute indexrange for this higher level tile.
    bounds = tile_bounds(tilex, tiley, tilez)
    # Get tile bounding box as ewkt.
    bounds = 'SRID={0};{1}'.format(WEB_MERCATOR_SRID, Envelope(bounds).wkt)
    # Get composite tile for this composite.
    ctile = get_composite_tile(composite_id, tilez, tilex, tiley)
    # Get queryset for sentineltiles within the composite date range.
    sentineltiles = ctile.composite.get_sentineltiles().filter(tile_data_geom__bboverlaps=bounds)
    # Get raw image arrays from tiles.
    raw = get_tiles(sentineltiles, tilez, tilex, tiley)
    # Convert the GDALRaster tiles into one image with padded RGB images and
    # the scene class as rows.
    return construct_image_from_tiles(raw)
