import os
import pickle
from collections import OrderedDict

import matplotlib.pyplot as plt
import numpy
from matplotlib.colors import LogNorm

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
    tess.construct_training_data(dat['targets'], dat['agglayer'], -20, time=True)
    #tess.construct_training_data(dat['targets'], dat['agglayer'], -20, dat['mask'].bands[0].data().ravel() == 2, time=True)

    # Stack the additional training data into the final matrix.
    global_train_x = numpy.vstack((global_train_x, tess.train_x))
    global_train_y = numpy.hstack((global_train_y, tess.train_y))

print('Found {} training pixels.'.format(len(global_train_y)))

##########
print('OLS')
#Y = [float(y) for y in global_train_y]
Y = [(float(d.strftime("%j"))-1) / 366 + float(d.strftime("%Y")) for d in global_train_y]
X = sm.add_constant(global_train_x)
model = sm.OLS(Y, X)
results = model.fit()
print(results.summary())

##########
print('Random Forest Regressor')
tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')
tess.train_x = global_train_x
tess.train_y = numpy.copy(global_train_y)
tess.train_y = numpy.array([(float(d.strftime("%j"))-1) / 366 + float(d.strftime("%Y")) for d in tess.train_y])
tess.classify(splitfraction=0.5, clf_name='rfr')
predicted = tess.clf.predict(tess.train_x[numpy.logical_not(tess._selector), :])
print('R-squared', tess.clf.score(tess.train_x[numpy.logical_not(tess._selector), :], tess.train_y[numpy.logical_not(tess._selector)]))
plt.hist2d(predicted, tess.train_y[numpy.logical_not(tess._selector)], (70, 70), cmap=plt.cm.jet)
plt.savefig('year-matrix-plot.png', dpi=600)
plt.clf()
plt.hist2d(predicted, tess.train_y[numpy.logical_not(tess._selector)], (70, 70), cmap=plt.cm.jet, norm=LogNorm())
plt.savefig('year-matrix-plot-norm.png', dpi=600)
algo = 'rfr'
for region, dat in regions.items():
    region_key = '-'.join(region.split(' ')[1:]).lower()
    print('Predicting', algo, region_key)
    # Get targets from disk.
    dat['targets'] = tess.read_target_rasters_from_disk(region_key)
    # Mask with forest area.
    mask = GDALRaster(os.path.join(os.getcwd(), 'sentinel-{}-predicted-svm.tif'.format(region_key)))
    mask = numpy.in1d(mask.bands[0].data().ravel(), [2, 3])

    #tess.predict_raster(dat['targets'], dat['bbox'], algo, region_key + '-age', datatype='float')
    tess.predict_raster(dat['targets'], dat['bbox'], algo, region_key + '-age', forest_mask=mask, datatype='float32')

##########
for algo in ['rf']:
    print('Classifying', algo)
    tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')
    tess.train_x = global_train_x
    tess.type_dict = OrderedDict([(str(yr.year), yr.year) for yr in numpy.unique(global_train_y)])
    tess.train_y = numpy.copy(global_train_y)
    tess.train_y = numpy.array([float(d.strftime("%Y")) for d in tess.train_y])
    print(numpy.unique(tess.train_y))
    print(tess.type_dict)

    tess.classify(splitfraction=0.5, clf_name=algo)

    print(tess.accuracy())

    print('Accuracy by class')
    tess.train_y = numpy.copy(global_train_y)
    tess.train_y = numpy.array([float(d.strftime("%Y")) for d in tess.train_y])
    dat = numpy.copy(tess.train_y)
    tess.train_y[dat > 2015] = 1
    tess.train_y[numpy.logical_and(dat <= 2015, dat > 2011)] = 2
    tess.train_y[dat <= 2011] = 3
    tess.type_dict = OrderedDict([('Cut', 1), ('Young', 2), ('Old', 3)])
    tess.classify(splitfraction=0.5, clf_name=algo)
    print(tess.accuracy())

    for region, dat in regions.items():
        region_key = '-'.join(region.split(' ')[1:]).lower()
        print('Predicting', algo, region_key)
        # Get targets from disk.
        dat['targets'] = tess.read_target_rasters_from_disk(region_key)
        # Mask with forest area.
        mask = GDALRaster(os.path.join(os.getcwd(), 'sentinel-{}-predicted-svm.tif'.format(region_key)))
        mask = numpy.in1d(mask.bands[0].data().ravel(), [2, 3])

        #tess.predict_raster(dat['targets'], dat['bbox'], algo, region_key + '-age-class')
        tess.predict_raster(dat['targets'], dat['bbox'], algo, region_key + '-age-class', forest_mask=mask)
