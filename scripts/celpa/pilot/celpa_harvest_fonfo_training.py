import os
import pickle
from collections import OrderedDict

import numpy

import tesselate
from django.contrib.gis.gdal import GDALRaster

os.chdir('/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports')

# GET MISSING BANDS
# # Create initial regions dict.
# regions = {
#     'Celpa Aveiro': {'scene_id': 138594, 'scene_date': '2017/11/14'},
#     'Celpa Castelo Branco': {'scene_id': 139061, 'scene_date': '2017/11/16'},
#     'Celpa Evora': {'scene_id': 140004, 'scene_date': '2017/11/16'},
#     'Celpa Faro': {'scene_id': 138255, 'scene_date': '2017/11/16'},
#     'Celpa Leiria': {'scene_id': 138259, 'scene_date': '2017/11/16'},
#     'Celpa Santarem': {'scene_id': 138239, 'scene_date': '2017/11/16'},
# }
#
# for region, dat in regions.items():
#     region_key = '-'.join(region.split(' ')[1:]).lower()
#     print(region_key)
#
#     tess = tesselate.Tesselo('ed28f33c9fb699d92965c0cd3714e274a11bce2c')
#     tess.bands_to_include = ('B01', 'B09', 'B10', )
#     # Get scene.
#     dat['scene'] = tess.get_scene(dat['scene_id'])
#     # Get aggregationlayers
#     dat['agglayers'] = tess.get_aggregationlayers(region)
#     # Reduce to first one found.
#     dat['agglayer'] = dat['agglayers'][0]
#     dat['bbox'] = tess.aggregationlayer_bbox(dat['agglayer'])
#     # Get targets from api.
#     dat['targets'] = tess.create_target_rasters(dat['bbox'], region_key=region_key)
#     tess.load_tile_data(dat['targets'], dat['bbox'], dat['scene'])


# Training
regions = pickle.load(open('regions.pickle', 'rb'))

# bands_to_include =  ('B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B09', 'B10', 'B11', 'B12', )
tess = tesselate.Tesselo('')
global_train_x = numpy.empty((len(tess.bands_to_include), 0)).T
global_train_y = numpy.empty((0, ))

for region, dat in regions.items():
    region_key = '-'.join(region.split(' ')[1:]).lower()
    print('Opening data for', region_key)

    tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')
    tess.type_dict = OrderedDict([('Non forest', 1), ('forest', 2)])
    # tess.bands_to_include = bands_to_include

    # Get targets from disk.
    dat['targets'] = tess.read_target_rasters_from_disk(region_key)

    # Create training dataset.
    tess.construct_training_data(dat['targets'], '/media/tam/rhino/work/projects/tesselo/celpa/analysis/training/celpa_forest_non_forest.shp', 0)

    # Stack the additional training data into the final matrix.
    global_train_x = numpy.vstack((global_train_x, tess.train_x))
    global_train_y = numpy.hstack((global_train_y, tess.train_y))

# Train and predict
os.chdir('/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/harvest')

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

for algo in ('rf', 'svmc', ):
    print('Classifying', algo)

    tess = tesselate.Tesselo('ed28f33c9fb699d92965c0cd3714e274a11bce2c')
    tess.type_dict = OrderedDict([('Non forest', 1), ('forest', 2)])

    tess.train_x = global_train_x
    tess.train_y = global_train_y

    tess.classify(splitfraction=0.5, clf_name=algo)
    print(tess.accuracy())

    with open('fonfo-{}.pickle'.format(algo), 'wb') as f:
        pickle.dump(tess.clf, f)

    for date, scene_id in scenes.items():
        print(date)

        targets = tess.read_target_rasters_from_disk(date)

        tess.predict_raster(targets, bbox, algo, date + '-fonfo')

dates = [
    '2016-12-06',
    '2016-12-26',
    '2017-01-05',
    '2017-01-15',
    '2017-01-25',
    '2017-02-24',
    '2017-03-16',
]

for index, date in enumerate(dates):
    print(index)
    after = GDALRaster(os.path.join(os.getcwd(), 'sentinel-{}-fonfo-predicted-rf.tif'.format(dates[index])))
    if index == 0:
        total = after.warp({'name': os.path.join(os.getcwd(), 'sentinel-total-fonfo-diff-rf.tif'.format(dates[index])), 'driver': 'tiff'})
        total.bands[0].data([0], shape=(1, 1))
        total_data = total.bands[0].data()
        print(total_data)
        continue

    before = GDALRaster(os.path.join(os.getcwd(), 'sentinel-{}-fonfo-predicted-rf.tif'.format(dates[index - 1])))


    diff = (after.bands[0].data() + 10) - before.bands[0].data()

    GDALRaster({
        'name': os.path.join(os.getcwd(), 'sentinel-{}-fonfo-diff-rf.tif'.format(dates[index])),
        'driver': 'tif',
        'datatype': before.bands[0].datatype(),
        'origin': before.origin,
        'width': before.width,
        'height': before.height,
        'srid': 3857,
        'scale': before.scale,
        'bands': [{'data': diff, }],
        'papsz_options': {
            'compress': 'deflate',
        }
    })
    total_data[diff==9] = index
    print(total_data)

total.bands[0].data(total_data)

# Total change
# before = GDALRaster(os.path.join(os.getcwd(), 'sentinel-{}-fonfo-predicted-rf.tif'.format(dates[0])))
# after = GDALRaster(os.path.join(os.getcwd(), 'sentinel-{}-fonfo-predicted-rf.tif'.format(dates[-1])))
#
# diff = (after.bands[0].data() + 10) - before.bands[0].data()
