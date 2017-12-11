import tesselate
from django.contrib.gis.gdal import GDALRaster
import os
from raster.tiles.utils import tile_bounds, tile_index_range, tile_scale
from raster.tiles.const import WEB_MERCATOR_TILESIZE
import numpy

tess = tesselate.Tesselo('e76280dd3a75e523e3986f3c0a40c879b98ac065')  # Daniel
#tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')  # Celpa
tess.zoom = 10

bbox = (-1071952.884671312, 4410322.392731305, -676314.8262672396, 5203974.322189415)

origin, width, height, scale = tess._get_geotransform(bbox)

print('Width/Height', width, height)

tile_range = tile_index_range(bbox, tess.zoom)

print('Tilex/Tiley', 1 + tile_range[2] - tile_range[0], 1 + tile_range[3] - tile_range[1])

nr_of_tiles = (1 + tile_range[2] - tile_range[0]) * (1 + tile_range[3] - tile_range[1])
print('Nr of Tiles', nr_of_tiles)

os.chdir('/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports')

worldlayers = {
    'november': {
        "name": "November 2017",
        "kahunas": {
            "B09.jp2": 45991,
            "B02.jp2": 45983,
            "B03.jp2": 45984,
            "B05.jp2": 45986,
            "B01.jp2": 45982,
            "B11.jp2": 45993,
            "B06.jp2": 45987,
            "B04.jp2": 45985,
            "B10.jp2": 45992,
            "B8A.jp2": 45990,
            "B12.jp2": 45994,
            "B08.jp2": 45989,
            "B07.jp2": 45988
        },
    },
    'june': {
        "name": "June 2017",
        "kahunas": {
            "B09.jp2": 170991,
            "B02.jp2": 170983,
            "B03.jp2": 170984,
            "B05.jp2": 170986,
            "B01.jp2": 170982,
            "B11.jp2": 170993,
            "B06.jp2": 170987,
            "B04.jp2": 170985,
            "B10.jp2": 170992,
            "B8A.jp2": 170990,
            "B12.jp2": 170994,
            "B08.jp2": 170989,
            "B07.jp2": 170988
        },
    #target = GDALRaster(raster_name, write=True)

    }
}


formula='(B8-B12)/(B8%2BB12)'  # Normalized Burn Ratio

for period, worldlayer in worldlayers.items():
    layers = 'B8={},B12={}'.format(worldlayer['kahunas']['B08.jp2'], worldlayer['kahunas']['B12.jp2'])
    # Create or open raster
    print('Processing period', period)
    raster_name = os.path.join(os.getcwd(), 'portugal-nbr-{}-zl{}.tif'.format(period, tess.zoom))
    #target = GDALRaster(raster_name, write=True)
    target = GDALRaster({
        'name': raster_name,
        'driver': 'tif',
        'datatype': 6,  # Float32
        'origin': origin,
        'width': width,
        'height': height,
        'srid': 3857,
        'scale': (scale, -scale),
        'bands': [{'data': [0], 'size': (1, 1), 'nodata_value': 0}],
        'papsz_options': {
            'compress': 'deflate',
        }
    })
    counter = 0
    for tilex in range(tile_range[0], tile_range[2] + 1):
        for tiley in range(tile_range[1], tile_range[3] + 1):

            if counter % 100 == 0:
                print('Processed {} tiles in {} ({}/{}).'.format(100.0 * counter / nr_of_tiles, period, counter, nr_of_tiles))
            counter += 1

            url = 'algebra/{z}/{x}/{y}.tif?layers={layers}&formula={formula}'.format(
                z=tess.zoom,
                x=tilex,
                y=tiley,
                layers=layers,
                formula=formula,
            )

            data = tess.get(url, json_response=False)

            # Open response as GDALRaster.
            rst = GDALRaster(data)

            # Open as GDAL raster and print to screen.
            xoffset = (tilex - tile_range[0]) * WEB_MERCATOR_TILESIZE
            yoffset = (tiley - tile_range[1]) * WEB_MERCATOR_TILESIZE

            target.bands[0].data(
                rst.bands[0].data().astype('float32'),
                size=(WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE),
                offset=(xoffset, yoffset),
            )


print('Computing diff locally')
before = GDALRaster(os.path.join(os.getcwd(), 'portugal-nbr-june-zl{}.tif'.format(tess.zoom)))
after = GDALRaster(os.path.join(os.getcwd(), 'portugal-nbr-november-zl{}.tif'.format(tess.zoom)))
target = GDALRaster({
    'name': 'portugal-nbr-diff-zl{}.tif'.format(tess.zoom),
    'driver': 'tif',
    'datatype': 6,
    'origin': origin,
    'width': width,
    'height': height,
    'srid': 3857,
    'scale': (scale, -scale),
    'bands': [{'data': [0], 'size': (1, 1), 'nodata_value': 0}],
    'papsz_options': {
        'compress': 'deflate',
    }
})

counter = 0
for tilex in range(tile_range[0], tile_range[2] + 1):
    for tiley in range(tile_range[1], tile_range[3] + 1):

        if counter % 100 == 0:
            print('Processed {} tiles ({}/{}).'.format(100.0 * counter / nr_of_tiles, counter, nr_of_tiles))
        counter += 1


        # Open as GDAL raster and print to screen.
        xoffset = (tilex - tile_range[0]) * WEB_MERCATOR_TILESIZE
        yoffset = (tiley - tile_range[1]) * WEB_MERCATOR_TILESIZE

        before_tile = before.bands[0].data(
            size=(WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE),
            offset=(xoffset, yoffset),
        )
        after_tile = after.bands[0].data(
            size=(WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE),
            offset=(xoffset, yoffset),
        )
        diff = (after_tile - before_tile).astype('float32')
        # We need to apply the thresholding proposed by the USGS FireMon program
        # < -0.25	High post-fire regrowth
        # -0.25 to -0.1	Low post-fire regrowth
        # -0.1 to +0.1	Unburned
        # 0.1 to 0.27	Low-severity burn
        # 0.27 to 0.44	Moderate-low severity burn
        # 0.44 to 0.66	Moderate-high severity burn
        # > 0.66	High-severity burn
        #diff_cat = numpy.zeros((WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE), 'uint8')
        #diff_cat[numpy.logical_and(diff > 0.1, diff <= 0.27)] = 1
        #diff_cat[numpy.logical_and(diff > 0.27, diff <= 0.44)] = 2
        #diff_cat[numpy.logical_and(diff > 0.44, diff <= 0.66)] = 3
        #diff_cat[diff > 0.66] = 4

        target.bands[0].data(
            diff,
            size=(WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE),
            offset=(xoffset, yoffset),
        )
