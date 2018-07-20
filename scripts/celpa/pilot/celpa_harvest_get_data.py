import os
import pickle
from collections import OrderedDict

import numpy
from raster.tiles.const import WEB_MERCATOR_SRID

import tesselate
from django.contrib.gis.gdal import GDALRaster, OGRGeometry

os.chdir('/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/harvest')

#'Celpa Aveiro': {'scene_id': 138595, 'scene_date': '2017/11/16'},

# Create initial regions dict.
scenes = {
    '2016-12-06': 153075,
    '2016-12-26': 153072,
    '2017-01-05': 153144,
    '2017-01-15': 153138,
    '2017-01-25': 153141,
    '2017-02-24': 153150,
    '2017-03-16': 153156,
}

tess = tesselate.Tesselo('ed28f33c9fb699d92965c0cd3714e274a11bce2c')
agglayer = tess.get_aggregationlayers('Gorgulho Leiria')[0]
# Reduce to first one found.
bbox = OGRGeometry.from_bbox(agglayer['extent'])
bbox.srid = 4326
bbox.transform(WEB_MERCATOR_SRID)

for date, scene_id in scenes.items():
    print(date)
    # Get scene.
    scene = tess.get_scene(scene_id)
    # Get targets from api.
    targets = tess.create_target_rasters(bbox, region_key=date)
    tess.load_tile_data(targets, bbox, scene)
    tess.export_rgb(targets, bbox, date)
