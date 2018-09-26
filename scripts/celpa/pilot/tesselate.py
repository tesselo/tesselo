import datetime
import os
import urllib
from collections import OrderedDict

import matplotlib.pyplot as plt
import numpy
import pandas
import requests
from raster.rasterize import rasterize
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import tile_bounds, tile_index_range, tile_scale
from sklearn import svm
from sklearn.ensemble import AdaBoostClassifier, BaggingClassifier, RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, cohen_kappa_score
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier

from django.conf import settings
from django.contrib.gis.gdal import DataSource, GDALRaster, OGRGeometry
from django.contrib.gis.geos import GEOSGeometry
from geomet import wkt

CELPA_CLASSES = {
    "Acacia": "Other Trees",
    "Aguas Interiores": "Water",
    "Amieiro": "Other Trees",
    "Arvores de Fruto": "Other Trees",
    "Azinheira": "Other Trees",
    "Borrazeira negra": "Other Trees",
    "Caminhos e Aceiros": "Shrub",
    "Carvalho cerquinho": "Other Trees",
    "Carvalho roble": "Other Trees",
    "Culturas Arvenses": "Arable Crops",
    "Edificacoes": "Buildings",
    "Estevas": "Shrub",
    "Eucalipto globulus": "Eucaliptus",
    "Eucalipto nitens": "Eucaliptus",
    "Floresta ribeirinha": "Other Trees",
    "Freixo comum": "Other Trees",
    "Linhas electricas": "Shrub",
    "Matos": "Shrub",
    "Outras Folhosas": "Other Trees",
    "Outras Infraestruturas": "Buildings",
    "Outros Eucaliptos": "Eucaliptus",
    "Pastagens": "Shrub",
    "Pinheiro bravo": "Pine",
    "Pinheiro Bravo": "Pine",
    "Pinheiro Manso": "Pine",
    "Recodificar": "Shrub",
    "Sobreiro": "Cork",
    "Tojo": "Other Trees",
    "Urze": "Other Trees",
}

TYPE_DICT = OrderedDict(sorted({
    'Eucaliptus 0': 1,
    'Eucaliptus 3': 2,
    'Eucaliptus >3': 3,
    'Pine': 4,
    'Cork': 5,
    'Other Trees': 6,
    'Shrub': 7,
    'Arable Crops': 8,
    'Buildings': 9,
    'Water': 10,
}.items(), key=lambda t: t[1]))


def qgis_style():
    fl = '# Python Generated QGis Color Map File\nINTERPOLATION:INTERPOLATED'
    colors = ['158,1,66', '213,62,79', '244,109,67', '253,174,97', '254,224,139', '230,245,152', '171,221,164', '102,194,165', '50,136,189', '94,79,162']
    for key,val in TYPE_DICT.items():
        fl += '\n{val},{col},255,{key}'.format(
            val=val,
            col=colors[val - 1],
            key=key
        )
    print(fl)


class Tesselo(object):

    api = 'https://tesselo.com/api/'

    bands_to_include = ('B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B11', 'B12', 'NDVI', 'EVI', )

    zoom = 14

    raster_basename = 'sentinel'

    raster_datatype = 'float32'
    raster_datatype_gdal = 6

    type_dict = TYPE_DICT

    def __init__(self, token):
        # Initiate session with token.
        self.session(token)

        # For the raster tilesize function.
        try:
            settings.configure()
        except:
            pass

    def api_url(self, url):
        return self.api + url

    def session(self, token):
        """
        Initiate requests session with a standard token-based authorization header.
        """
        auth_header = {'Authorization': 'Token {}'.format(token)}

        self.session = requests.Session()
        self.session.headers.update(auth_header)

    def get(self, url, json_response=True):
        """
        Make a get request to api. Assumes json response. The input url can be passed
        without api root.
        """
        # Add api root if its not part of the url.
        if not url.startswith(self.api):
            url = self.api + url

        # Get response.
        response = self.session.get(url)

        # Check for errors in response.
        response.raise_for_status()

        if json_response:
            return response.json()
        else:
            return response.content

    def get_aggregationlayers(self, search=''):
        """
        Get aggregationlayers, optinally filter by name or description.
        """
        agglayers = self.get('aggregationlayer?search={}'.format(search))

        if agglayers['count']:
            return agglayers['results']

    def aggregationlayer_bbox(self, aggregationlayer):
        """
        Construct bounding box around the aggregationlayer.
        """
        xmins = []
        ymins = []
        xmaxs = []
        ymaxs = []

        url = 'aggregationarea/{}'

        # Get range of coords for each aggregationarea around aggregationlayer.
        for agg in aggregationlayer['aggregationareas']:
            coords = self.get(url.format(agg))['geom']['coordinates'][0][0]

            xmins.append(min([coord[0] for coord in coords]))
            ymins.append(min([coord[1] for coord in coords]))
            xmaxs.append(max([coord[0] for coord in coords]))
            ymaxs.append(max([coord[1] for coord in coords]))

        # Construct geom from coords range.
        bbox = (min(xmins), min(ymins), max(xmaxs), max(ymaxs))
        bbox = OGRGeometry.from_bbox(bbox)
        bbox.srid = 4326
        bbox.transform(WEB_MERCATOR_SRID)

        return bbox

    def _get_raster_name(self, region_key):
        name = self.raster_basename
        if region_key:
            name += '-' + region_key
        return name

    def _get_geotransform(self, bbox):
        """
        Compute geotransform parameters for target rasters based on bbox and zoom.
        """
        if not isinstance(bbox, (tuple, list)):
            bbox = bbox.extent
        tile_range = tile_index_range(bbox, self.zoom)
        scale = tile_scale(self.zoom)
        bnds = tile_bounds(tile_range[0], tile_range[1], self.zoom)
        origin = (bnds[0], bnds[3])
        xlen = tile_range[2] - tile_range[0] + 1
        ylen = tile_range[3] - tile_range[1] + 1
        width = xlen * WEB_MERCATOR_TILESIZE
        height = ylen * WEB_MERCATOR_TILESIZE

        return origin, width, height, scale

    def create_target_rasters(self, bbox, region_key=None):
        """
        Create empty target rasters on disk for all bands. The empty rasters
        will be populated with tile data in a second step.
        """
        origin, width, height, scale = self._get_geotransform(bbox)

        # Prepare raster name and target dict.
        name = self._get_raster_name(region_key)
        targets = OrderedDict()

        for bnd in self.bands_to_include:
            targets[bnd + '.jp2'] = GDALRaster({
                'name': os.path.join(os.getcwd(), '{}-{}.tif'.format(name, bnd.lower())),
                'driver': 'tif',
                'datatype': self.raster_datatype_gdal,
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

        return targets

    def read_target_rasters_from_disk(self, region_key=None):
        """
        Reload target rasters from local disk.
        """
        name = self._get_raster_name(region_key)
        targets = OrderedDict()
        for bnd in self.bands_to_include:
            targets[bnd + '.jp2'] = GDALRaster(os.path.join(os.getcwd(), '{}-{}.tif'.format(name, bnd.lower())))
        return targets

    def get_scene(self, pk):
        # Get rasterlayer ids for a sentinel scene over the aggregationlayer.
        # EVORA tiles/29/S/NC/2017/11/16/0/  pk_evora = 140004
        return self.get('sentineltileaggregationlayer/{}'.format(pk))

    def load_tile_data(self, targets, bbox, scene):
        """
        Populates pixel values for target rasters based on tiles over bbox,
        and stitches them together.
        """
        tile_range = tile_index_range(bbox.extent, self.zoom)

        # Get tiles for each band and stitch them together.
        for bnd, rast in targets.items():

            if bnd == 'NDVI.jp2':
                layers = 'B8={},B4={}'.format(scene['rasterlayer_lookup']['B08.jp2'], scene['rasterlayer_lookup']['B04.jp2'])
                formula = urllib.parse.quote('(B8-B4)/(B8+B4)', safe='()/')
            elif bnd == 'EVI.jp2':
                layers = 'B8={},B4={}'.format(scene['rasterlayer_lookup']['B08.jp2'], scene['rasterlayer_lookup']['B04.jp2'])
                formula = urllib.parse.quote('(2.5*(B8-B4)/(B8+2.4*B4+1))', safe='()/*')
            else:
                layers = 'x={}'.format(scene['rasterlayer_lookup'][bnd])
                formula = 'x'

            print('Getting tiles for', layers, formula)

            for xtile in range(tile_range[0], tile_range[2] + 1):
                for ytile in range(tile_range[1], tile_range[3] + 1):

                    url = 'algebra/{z}/{x}/{y}.tif?layers={layers}&formula={formula}'.format(
                        z=self.zoom,
                        x=xtile,
                        y=ytile,
                        layers=layers,
                        formula=formula,
                    )

                    data = self.get(url, json_response=False)

                    # Open response as GDALRaster.
                    rst = GDALRaster(data)

                    # Open as GDAL raster and print to screen.
                    xoffset = (xtile - tile_range[0]) * WEB_MERCATOR_TILESIZE
                    yoffset = (ytile - tile_range[1]) * WEB_MERCATOR_TILESIZE

                    targets[bnd].bands[0].data(
                        rst.bands[0].data().astype(self.raster_datatype),
                        size=(WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE),
                        offset=(xoffset, yoffset),
                    )

    def export_rgb(self, targets, bbox, region_key):
        """
        Create rgb version of region.
        """
        name = self._get_raster_name(region_key)

        origin, width, height, scale = self._get_geotransform(bbox)

        rgb = GDALRaster({
            'name': os.path.join(os.getcwd(), '{}-rgb.tif'.format(name)),
            'driver': 'tif',
            'datatype': self.raster_datatype_gdal,
            'origin': origin,
            'width': width,
            'height': height,
            'srid': 3857,
            'scale': (scale, -scale),
            'bands': [{'data': [0], 'size': (1, 1), 'nodata_value': 0}] * 3,
            'papsz_options': {
                'compress': 'deflate',
            }
        })

        rgb.bands[0].data(targets['B04.jp2'].bands[0].data())
        rgb.bands[1].data(targets['B03.jp2'].bands[0].data())
        rgb.bands[2].data(targets['B02.jp2'].bands[0].data())

        print('Finished RGB export.')

    def _get_geoms_from_ggregationlayer(self, aggregationlayer):

        for agg in aggregationlayer['aggregationareas']:

            agg_area = self.get('aggregationarea/{}'.format(agg))

            # Standardize agg types.
            agg_type = None
            for key, val in CELPA_CLASSES.items():
                if key in agg_area['name']:
                    agg_type = val

            if not agg_type:
                raise ValueError('Could not standardize class for {}.'.format(agg_area['name']))

            # Differenciate Eucaliptus by age.
            if agg_type == 'Eucaliptus':
                yr = int(agg_area['attributes']['year'])
                if yr >= 2016:
                    agg_type += ' 0'
                elif yr >= 2012:
                    agg_type += ' 3'
                else:
                    agg_type += ' >3'

            # Construct the aggregationarea geom object in web mercator projection.
            geom = wkt.dumps(agg_area['geom'])
            geom = GEOSGeometry(geom)
            geom.srid = 4326
            geom.transform(WEB_MERCATOR_SRID)

            yield agg_type, geom, agg_area['attributes']

    def _get_geoms_from_shapefile(self, shapefile):

        ds = DataSource(shapefile)
        lyr = ds[0]
        for feat in lyr:
            yield feat.get('name'), feat.geom.geos, {}


    def construct_training_data(self, targets, aggregationlayer, buffer_radius=-30, forest_mask=None, time=False):

        type_count = 0

        train_x = numpy.empty((len(targets), 0))
        train_y = numpy.empty((0, ))

        if isinstance(aggregationlayer, str):
            iterator = self._get_geoms_from_shapefile
        else:
            iterator = self._get_geoms_from_ggregationlayer

        old_count = 0
        for agg_type, geom, attributes in iterator(aggregationlayer):
            if time and not 'Eucaliptus' in agg_type:
                continue

            # Use a negative buffer to avoid mixed boundary pixels.
            if buffer_radius:
                buff = geom.buffer(buffer_radius)
            else:
                buff = geom

            # Create a mask array for the geometry over the target areas.
            mask = rasterize(buff, next(iter(targets.values()))).bands[0].data().ravel().astype('bool')

            # Mask out non-forest areas if mask is provided.
            if forest_mask is not None:
                mask = mask * forest_mask

            # Extract pixel values for all bands using geometry mask.
            vals = [rst.bands[0].data().ravel()[mask] for rst in targets.values()]

            if time:
                # For timeseries, set the y values to the observation time.
                try:
                    year = datetime.datetime.strptime(attributes['DATA_REF'], '%d-%m-%Y').date()
                    if year < datetime.date(2006, 1, 1):
                        old_count += len(vals[0])
                        continue
                    #type_array = numpy.array([datetime.datetime.strptime(attributes['DATA_REF'], '%d-%m-%Y')] * len(vals[0]))
                    type_array = numpy.array([year] * len(vals[0]))
                except:
                    print('Could not convert timestamp', attributes['DATA_REF'])
                    raise
            else:
                # Construct array with the category class.
                type_array = numpy.ones(len(vals[0])).astype('float32') * self.type_dict[agg_type]

            # Stack the additional training data into the final matrix.
            train_x = numpy.hstack((train_x, vals))
            train_y = numpy.hstack((train_y, type_array))

        if old_count > 0:
            print('Skipped {} pixels from before 2006.'.format(old_count))

        # Transpose training matrix for use with classifiers.
        self.train_x = train_x.T
        self.train_y = train_y

    _selector = None

    def classify(self, splitfraction=0.5, clf_name='rf'):
        # Create split selector.
        if self._selector is None:
            self._selector = numpy.random.random(len(self.train_y)) > splitfraction

        # Extract training part of dataset.
        train_y_s = self.train_y[self._selector]
        train_x_s = self.train_x[self._selector, :]

        print('Using split franction:', round(float(len(train_y_s)) / len(self.train_y), 2), ' (', len(train_y_s), ' pixels).')

        # Instantiate classifier.
        if clf_name == 'rf':
            self.clf = RandomForestClassifier(n_estimators=10, max_depth=None, min_samples_split=2, random_state=0)
        elif clf_name == 'rfr':
            self.clf = RandomForestRegressor()
        elif clf_name == 'svmc':
            self.clf = svm.SVC(kernel='linear', C=0.01)
        elif clf_name == 'svm':
            self.clf = svm.LinearSVC(C=0.01)
        elif clf_name == 'nn':
            #self.clf = MLPClassifier(solver='sgd', alpha=1e-5, hidden_layer_sizes=(200, 100, 100, 100), learning_rate_init= 0.095, learning_rate='adaptive', max_iter=500)
            self.clf = MLPClassifier(solver='adam', alpha=1e-5, hidden_layer_sizes=(200, 100, 100), max_iter=500)
        elif clf_name == 'bag':
            self.clf = BaggingClassifier(KNeighborsClassifier(), max_samples=0.05, max_features=0.75)
        elif clf_name == 'ada':
            self.clf = AdaBoostClassifier(n_estimators=100)
        else:
            raise ValueError('Could not find classifier {}'.format(clf_name))

        # Fit classifier.
        self.clf.fit(train_x_s, train_y_s)

    def accuracy(self):
        """
        Accuracy assessment of classifier.
        """
        predicted = self.clf.predict(self.train_x[numpy.logical_not(self._selector), :])
        control = self.train_y[numpy.logical_not(self._selector)]

        lookup = {val: key for key, val in self.type_dict.items()}

        y_pred = pandas.Series([lookup[key] for key in predicted])
        y_true = pandas.Series([lookup[key] for key in control])

        print('Accuracy score:', accuracy_score(predicted, control))
        print('Cohen Kappa:   ', cohen_kappa_score(predicted, control))

        return pandas.crosstab(y_true, y_pred, rownames=['True'], colnames=['Predicted'], margins=True)#, normalize='columns')

    def predict_raster(self, targets, bbox, clf_name, region_key=None, plot=False, forest_mask=None, datatype='uint8'):
        """
        Export predicted raster.
        """
        name = self._get_raster_name(region_key)

        # Compute geotransform parameters for target rasters based on bbox and zoom.
        origin, width, height, scale = self._get_geotransform(bbox)

        predicted_raster = GDALRaster({
            'name': os.path.join(os.getcwd(), '{}-predicted-{}.tif'.format(name, clf_name)),
            'driver': 'tif',
            'datatype': 1 if datatype == 'uint8' else 6,
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

        # Get data from tiles.
        predictors = [rast.bands[0].data().ravel() for rast in targets.values()]

        # Convert predictor array to numpy array before passing it to predictor.
        predictors = numpy.array(predictors)

        # Predict values based on tile data.
        result = self.clf.predict(predictors.T)

        # Mask non-forest areas.
        if forest_mask is not None:
            result[numpy.logical_not(forest_mask)] = 0

        # Set data on predicted raster.
        result = result.reshape(predicted_raster.width, predicted_raster.height).astype('uint8' if datatype == 'uint8' else 'float32')
        predicted_raster.bands[0].data(result)

        print(predicted_raster.name)

        # Print raster to screen.
        if plot:
            plt.imshow(predicted_raster.bands[0].data())
            plt.show()


    def accuracy_by_geom(self, aggregationlayer, clf_name, region_keys):

        ref_cat = []
        pred_cat = []

        for region_key in region_keys:

            name = self._get_raster_name(region_key)
            predicted_raster = GDALRaster(os.path.join(os.getcwd(), '{}-predicted-{}.tif'.format(name, clf_name)))

            for agg_type, geom, attributes in self._get_geoms_from_ggregationlayer(aggregationlayer):

                # Compute equivalent class from celpa.
                ref = TYPE_DICT[agg_type]
                if ref not in [2, 3, 4, 5]:
                    ref = 0

                # Use a negative buffer to avoid mixed boundary pixels.
                buffer_radius = -30
                geom = geom.buffer(buffer_radius)
                if geom.empty:
                    continue

                # Create a mask array for the geometry over the target areas.
                mask = rasterize(geom, predicted_raster).bands[0].data().ravel().astype('bool')

                # Extract pixel values for all bands using geometry mask.
                vals = predicted_raster.bands[0].data().ravel()[mask]

                # Remove nodata pixels.
                vals = vals[vals != 0]

                if not len(vals):
                    majority = 0
                else:
                    # Compute majority class in this geom.
                    values, counts = numpy.unique(vals, return_counts=True)
                    index = numpy.argmax(counts)
                    majority = values[index]

                # Simplify categories.
                if ref == 2:
                    ref = 3
                if majority == 2:
                    majority = 3

                pred_cat.append(majority)
                ref_cat.append(ref)

        ref_cat = numpy.array(ref_cat)
        pred_cat = numpy.array(pred_cat)

        print('Accuracy score:', accuracy_score(pred_cat, ref_cat))
        print('Cohen Kappa:   ', cohen_kappa_score(pred_cat, ref_cat))
        print(pandas.crosstab(ref_cat, pred_cat, rownames=['True'], colnames=['Predicted'], margins=True))
