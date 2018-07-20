import os
import pickle
from collections import OrderedDict

import numpy

import tesselate

os.chdir('/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports')

regions = pickle.load(open('regions.pickle', 'rb'))

global_train_x = numpy.empty((len(tesselate.Tesselo('').bands_to_include), 0)).T
global_train_y = numpy.empty((0, ))


for region, dat in regions.items():
    region_key = '-'.join(region.split(' ')[1:]).lower()
    print('Opening data for', region_key)

    tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')
    tess.type_dict = OrderedDict([('Non forest', 1), ('forest', 2)])

    # Get targets from disk.
    dat['targets'] = tess.read_target_rasters_from_disk(region_key)

    # Create training dataset.
    tess.construct_training_data(dat['targets'], '/media/tam/rhino/work/projects/tesselo/celpa/analysis/training/celpa_forest_non_forest.shp', 0)

    # Stack the additional training data into the final matrix.
    global_train_x = numpy.vstack((global_train_x, tess.train_x))
    global_train_y = numpy.hstack((global_train_y, tess.train_y))


for algo in ('svm', 'rf'):
    print('Classifying', algo)

    tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')
    tess.type_dict = OrderedDict([('Non forest', 1), ('forest', 2)])

    tess.train_x = global_train_x
    tess.train_y = global_train_y

    tess.classify(splitfraction=0.5, clf_name=algo)
    print(tess.accuracy())

    for region, dat in regions.items():
        region_key = '-'.join(region.split(' ')[1:]).lower()
        print('Predicting', algo, region_key)
        # Get targets from disk.
        dat['targets'] = tess.read_target_rasters_from_disk(region_key)
        tess.predict_raster(dat['targets'], dat['bbox'], algo, region_key + '-fonfo')
