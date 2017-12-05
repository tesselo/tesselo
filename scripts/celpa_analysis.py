import os
import pickle
from collections import OrderedDict

import numpy

import tesselate
from django.contrib.gis.gdal import GDALRaster

os.chdir('/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports')

#'Celpa Aveiro': {'scene_id': 138595, 'scene_date': '2017/11/16'},

# Create initial regions dict.
#regions = {
    #'Celpa Aveiro': {'scene_id': 138594, 'scene_date': '2017/11/14'},
    #'Celpa Castelo Branco': {'scene_id': 139061, 'scene_date': '2017/11/16'},
    #'Celpa Evora': {'scene_id': 140004, 'scene_date': '2017/11/16'},
    #'Celpa Faro': {'scene_id': 138255, 'scene_date': '2017/11/16'},
    #'Celpa Leiria': {'scene_id': 138259, 'scene_date': '2017/11/16'},
    #'Celpa Santarem': {'scene_id': 138239, 'scene_date': '2017/11/16'},
#}

#for region, dat in regions.items():
    #region_key = '-'.join(region.split(' ')[1:]).lower()
    #print(region_key)

    #tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')

    ## Get scene.
    #dat['scene'] = tess.get_scene(dat['scene_id'])
    ## Get aggregationlayers
    #dat['agglayers'] = tess.get_aggregationlayers(region)
    ## Reduce to first one found.
    #dat['agglayer'] = dat['agglayers'][0]
    #dat['bbox'] = tess.aggregationlayer_bbox(dat['agglayer'])
    ## Get targets from api.
    #dat['targets'] = tess.create_target_rasters(dat['bbox'], region_key=region_key)
    #tess.load_tile_data(dat['targets'], dat['bbox'], dat['scene'])
    #tess.export_rgb(dat['targets'], dat['bbox'], region_key)

#with open('regions.pickle', 'wb') as f:
    #pickle.dump(regions, f)

regions = pickle.load(open('regions.pickle', 'rb'))

global_train_x = numpy.empty((len(tesselate.Tesselo('').bands_to_include), 0)).T
global_train_y = numpy.empty((0, ))

for region, dat in regions.items():

    region_key = '-'.join(region.split(' ')[1:]).lower()
    print('Opening data for', region_key)

    tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')
    tess.type_dict = OrderedDict([('eu', 3), ('euy', 2), ('pi', 4), ('sob', 5)])

    # Get targets from disk.
    dat['targets'] = tess.read_target_rasters_from_disk(region_key)

    # Mask with forest area.
    dat['mask'] = GDALRaster(os.path.join(os.getcwd(), 'sentinel-{}-fonfo-predicted-rf.tif'.format(region_key)))

    # Create training dataset.
    #tess.construct_training_data(dat['targets'], dat['agglayer'], -50, dat['mask'].bands[0].data().ravel() == 2)
    tess.construct_training_data(dat['targets'], '/media/tam/rhino/work/projects/tesselo/celpa/analysis/training/celpa_forest_type_manual.shp', 0)

    # Stack the additional training data into the final matrix.
    global_train_x = numpy.vstack((global_train_x, tess.train_x))
    global_train_y = numpy.hstack((global_train_y, tess.train_y))

# Classify and predict.
clsf = {}
for algo in ('nn', 'svm', 'rf'):
    print('Classifying', algo)

    tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')
    tess.type_dict = OrderedDict([('eu', 3), ('euy', 2), ('pi', 4), ('sob', 5)])
    tess.train_x = global_train_x
    tess.train_y = global_train_y

    tess.classify(splitfraction=0.8, clf_name=algo)
    print(tess.accuracy())

    clsf[algo] = tess.clf

    # Predict.
    continue
    for region, dat in regions.items():
        region_key = '-'.join(region.split(' ')[1:]).lower()
        print('Predicting', algo, region_key)
        # Get targets from disk.
        dat['targets'] = tess.read_target_rasters_from_disk(region_key)
        # Mask with forest area.
        dat['mask'] = GDALRaster(os.path.join(os.getcwd(), 'sentinel-{}-fonfo-predicted-svm.tif'.format(region_key)))
        tess.predict_raster(dat['targets'], dat['bbox'], algo, region_key, forest_mask=dat['mask'].bands[0].data().ravel() == 2)


global_train_x_celpa = numpy.empty((len(tesselate.Tesselo('').bands_to_include), 0)).T
global_train_y_celpa = numpy.empty((0, ))

for region, dat in regions.items():

    region_key = '-'.join(region.split(' ')[1:]).lower()
    print('Opening data for', region_key)

    # Get targets from disk.
    tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')
    dat['targets'] = tess.read_target_rasters_from_disk(region_key)
    dat['mask'] = GDALRaster(os.path.join(os.getcwd(), 'sentinel-{}-fonfo-predicted-rf.tif'.format(region_key)))
    tess.construct_training_data(dat['targets'], dat['agglayer'], -30, dat['mask'].bands[0].data().ravel() == 2)

    # Stack the additional training data into the final matrix.
    global_train_x_celpa = numpy.vstack((global_train_x_celpa, tess.train_x))
    global_train_y_celpa = numpy.hstack((global_train_y_celpa, tess.train_y))

for algo in ('nn', 'svm', 'rf'):

    print('Classifying', algo)

    tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')
    tess.type_dict = OrderedDict([('eu', 3), ('euy', 2), ('pi', 4), ('sob', 5)])
    tess.clf = clsf[algo]

    # Change type to simpler scheme.
    print('Before filter', numpy.unique(global_train_y_celpa), global_train_x_celpa.shape)

    del_index = numpy.in1d(global_train_y_celpa, numpy.array([2, 3, 4, 5]))

    tess.train_x = global_train_x_celpa[del_index]
    tess.train_y = global_train_y_celpa[del_index]

    tess._selector = [False] * len(tess.train_y)

    print(tess.accuracy())
