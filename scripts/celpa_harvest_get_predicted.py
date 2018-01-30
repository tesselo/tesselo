import requests
from raster.tiles.const import *
from raster.tiles.const import WEB_MERCATOR_SRID
from raster.tiles.utils import *

from django.conf import settings
from django.contrib.gis.gdal import GDALRaster, OGRGeometry

# Construct a standard token-based authorization header.
token = 'ed28f33c9fb699d92965c0cd3714e274a11bce2c'

auth_header = {'Authorization': 'Token {}'.format(token)}

# Set api host.
api = 'https://tesselo.com/api/'

# Setup requests session.
s = requests.Session()
s.headers.update(auth_header)

# Get the first available aggregationlayer.
search_for = 'Gorgulho Leiria'
agglayers = s.get(api + 'aggregationlayer?search={}'.format(search_for)).json()
print('Found {} aggregation layers.'.format(agglayers['count']))

# Reduce to first one found.
agglayer = agglayers['results'][0]
print(agglayer)

bbox = OGRGeometry.from_bbox(agglayer['extent'])
bbox.srid = 4326
bbox.transform(WEB_MERCATOR_SRID)
print(bbox)

try:
    settings.configure()
except:
    pass

zoom = 14
tile_range = tile_index_range(bbox.extent, zoom)
scale = tile_scale(zoom)
bnds = tile_bounds(tile_range[0], tile_range[1], zoom)
origin = (bnds[0], bnds[3])
xlen = tile_range[2] - tile_range[0] + 1
ylen = tile_range[3] - tile_range[1] + 1

print(tile_range, scale, bnds, origin, xlen, ylen)

# Prepare target rasters.
scale = tile_scale(zoom)

# Get tiles for each band and stitch them together.
# layer = 175195  # FonFo predicted RF
# layer = 183375  # FonFo predicted svm
# layer = 30715  # Red channel
# layer = 183377  # FonFo predicted RF Ordered
# layer = 183378  # FonFo predicted SVM Ordered
layers = [
    ('2016-12-06', 183379),
    ('2016-12-26', 183380),
    ('2017-01-05', 183381),
    ('2017-01-15', 183383),
    ('2017-01-25', 183377),
    ('2017-02-24', 183385),
    ('2017-03-16', 183386),
]

for index, (date, layer) in enumerate(layers):
    print(index, date, layer)

    target = GDALRaster({
        'name': '/home/tam/Desktop/fonfo-rf-{0}.tif'.format(date),
        'driver': 'tif',
        'datatype': 3,
        'origin': origin,
        'width': xlen * WEB_MERCATOR_TILESIZE,
        'height': ylen * WEB_MERCATOR_TILESIZE,
        'srid': 3857,
        'scale': (scale, -scale),
        'bands': [{'data': [0], 'size': (1, 1), 'nodata_value': 0}],
        'papsz_options': {
            'compress': 'deflate',
        }
    })

    for xtile in range(tile_range[0], tile_range[2] + 1):
        for ytile in range(tile_range[1], tile_range[3] + 1):
            print(xtile, ytile)
            response = s.get('https://tesselo.com/api/algebra/{z}/{x}/{y}.tif?layers=x={lyr}&formula=x'.format(
                z=zoom,
                x=xtile,
                y=ytile,
                lyr=layer,
            ))

            # Ensure we notice bad responses.
            response.raise_for_status()

            # Open response as GDALRaster.
            rst = GDALRaster(response.content)

            # Open as GDAL raster and print to screen.
            xoffset = (xtile - tile_range[0]) * WEB_MERCATOR_TILESIZE
            yoffset = (ytile - tile_range[1]) * WEB_MERCATOR_TILESIZE
            target.bands[0].data(
                rst.bands[0].data().astype('int16'),
                size=(WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE),
                offset=(xoffset, yoffset),
            )

for index, dat in enumerate(layers):
    if index == 0:
        continue
    print(index)
    before = GDALRaster('/home/tam/Desktop/fonfo-rf-{0}.tif'.format(layers[index - 1][0]))
    after = GDALRaster('/home/tam/Desktop/fonfo-rf-{0}.tif'.format(layers[index][0]))

    diff = after.bands[0].data() - before.bands[0].data()

    target = GDALRaster({
        'name': '/home/tam/Desktop/fonfo-diff-rf-{0}.tif'.format(layers[index][0]),
        'driver': 'tif',
        'datatype': 3,
        'origin': origin,
        'width': xlen * WEB_MERCATOR_TILESIZE,
        'height': ylen * WEB_MERCATOR_TILESIZE,
        'srid': 3857,
        'scale': (scale, -scale),
        'bands': [{'data': diff}],
        'papsz_options': {
            'compress': 'deflate',
        }
    })
