import os
import pickle
from collections import OrderedDict

import numpy
import statsmodels
import statsmodels.api as sm

import tesselate
from django.contrib.gis.gdal import GDALRaster

os.chdir('/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports')

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
    #tess.construct_training_data(dat['targets'], dat['agglayer'], -20, time=True)
    tess.construct_training_data(dat['targets'], dat['agglayer'], -50, dat['mask'].bands[0].data().ravel() == 2, time=True)

    # Stack the additional training data into the final matrix.
    global_train_x = numpy.vstack((global_train_x, tess.train_x))
    global_train_y = numpy.hstack((global_train_y, tess.train_y))

print('Found {} training pixels.'.format(len(global_train_y)))

Y = [float(y) for y in global_train_y]
X = sm.add_constant(global_train_x)
model = sm.OLS(Y, X)
results = model.fit()
print(results.summary())

# Classify.
for algo in ['rf']:
#for algo in ('nn', 'svm', 'rf'):
    print('Classifying', algo)

    tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')
    tess.type_dict = OrderedDict([(str(yr), yr) for yr in numpy.unique(global_train_y)])
    tess.train_x = global_train_x
    tess.train_y = global_train_y

    tess.classify(splitfraction=0.9, clf_name=algo)
    print(tess.accuracy())

    for region, dat in regions.items():
        region_key = '-'.join(region.split(' ')[1:]).lower()
        print('Predicting', algo, region_key)
        # Get targets from disk.
        dat['targets'] = tess.read_target_rasters_from_disk(region_key)
        # Mask with forest area.
        dat['mask'] = GDALRaster(os.path.join(os.getcwd(), 'sentinel-{}-fonfo-predicted-rf.tif'.format(region_key)))

        tess.predict_raster(dat['targets'], dat['bbox'], algo, region_key + '-age', datatype='float')
        #tess.predict_raster(dat['targets'], dat['bbox'], algo, region_key, forest_mask=dat['mask'].bands[0].data().ravel() == 2, datatype='float')
