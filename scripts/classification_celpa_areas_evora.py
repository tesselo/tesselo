import os
import urllib

import matplotlib.pyplot as plt
import numpy
import requests
from geomet import wkt
from raster.rasterize import rasterize
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import tile_bounds, tile_index_range, tile_scale
from sklearn import svm
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import cohen_kappa_score
from sklearn.neural_network import MLPClassifier

import pandas
from django.conf import settings
from django.contrib.gis.gdal import GDALRaster, OGRGeometry
from django.contrib.gis.geos import GEOSGeometry


class Tesselo(object):

    api = 'https://tesselo.com/api/'

    bands_to_include = ('B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'NDVI', 'EVI', )

    zoom = 14

    raster_basename = 'sentinel'

    raster_datatype = 'float32'
    raster_datatype_gdal = 6

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
        tile_range = tile_index_range(bbox.extent, self.zoom)
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
        targets = {}

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
        targets = {}
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
                layers = 'B8={},B4={}'.format(scene['kahunas']['B08.jp2'], scene['kahunas']['B04.jp2'])
                formula = urllib.parse.quote('(B8-B4)/(B8+B4)', safe='()/')
            elif bnd == 'EVI.jp2':
                layers = 'B8={},B4={}'.format(scene['kahunas']['B08.jp2'], scene['kahunas']['B04.jp2'])
                formula = urllib.parse.quote('(2.5*(B8-B4)/(B8+2.4*B4+1))', safe='()/*')
            else:
                layers = 'x={}'.format(scene['kahunas'][bnd])
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

    def construct_training_data(self, targets, aggregationlayer, buffer=-30):

        type_count = 0
        type_dict = {}

        train_x = numpy.empty((len(targets), 0))
        train_y = numpy.empty((0, ))

        for agg in aggregationlayer['aggregationareas']:

            agg_area = self.get('aggregationarea/{}'.format(agg))

            # Construct classification class name.
            agg_type = agg_area['name'].split(' ')

            if '-' in agg_type[-1]:
                agg_type = ' '.join(agg_type[1:-1])
            else:
                agg_type = ' '.join(agg_type[1:])

            # Check if class exists, otherwise add to dictionary.
            if agg_type not in type_dict:
                type_count += 1
                type_dict[agg_type] = type_count

            # Construct the aggregationarea geom object in web mercator projection.
            geom = wkt.dumps(agg_area['geom'])
            geom = GEOSGeometry(geom)
            geom.srid = 4326
            geom.transform(WEB_MERCATOR_SRID)

            # Use a negative buffer to avoid mixed boundary pixels.
            buff = geom.buffer(buffer)

            # Create a mask array for the geometry over the target areas.
            mask = rasterize(buff, next(iter(targets.values()))).bands[0].data().ravel().astype('bool')

            # Extract pixel values for all bands using geometry mask.
            vals = [rst.bands[0].data().ravel()[mask] for rst in targets.values()]

            # Construct array with the category class.
            type_array = numpy.ones(len(vals[0])).astype('float32') * type_dict[agg_type]

            # Stack the additional training data into the final matrix.
            train_x = numpy.hstack((train_x, vals))
            train_y = numpy.hstack((train_y, type_array))

        # Transpose training matrix for use with classifiers.
        self.train_x = train_x.T
        self.train_y = train_y
        self.type_dict = type_dict

        print(type_dict, train_x.shape, train_y.shape)

    _selector = None

    def classify(self, splitfraction=0.5, clf_name='rf'):
        # Create split selector.
        if not self._selector:
            self._selector = numpy.random.random(len(self.train_y)) > splitfraction

        # Extract training part of dataset.
        train_y_s = self.train_y[self._selector]
        train_x_s = self.train_x[self._selector, :]

        print('Using split franction:', round(float(len(train_y_s)) / len(self.train_y), 2))

        # Instantiate classifier.
        if clf_name == 'rf':
            self.clf = RandomForestClassifier(n_estimators=10, max_depth=None, min_samples_split=2, random_state=0)
        elif clf_name == 'svm':
            self.clf = svm.SVC(kernel='linear', C=0.01)
        elif clf_name == 'nn':
            raise NotImplementedError('Neural networks do not work at the moment.')
            self.clf = MLPClassifier(solver='lbfgs', alpha=1e-5, hidden_layer_sizes=(5, 2), random_state=1)

        # Fit classifier.
        self.clf.fit(train_x_s, train_y_s)

        print(self.clf)

    def accuracy(self):
        """
        Accuracy assessment of classifier.
        """
        predicted = self.clf.predict(self.train_x[numpy.logical_not(self._selector), :])
        control = self.train_y[numpy.logical_not(self._selector)]

        lookup = {val: '_'.join(key.split(' ')) for key, val in self.type_dict.items()}
        lookup = {val: key for key, val in self.type_dict.items()}

        y_pred = pandas.Series([lookup[key] for key in predicted])
        y_true = pandas.Series([lookup[key] for key in control])

        print('Kappa', cohen_kappa_score(predicted, control))

        return pandas.crosstab(y_true, y_pred, rownames=['True'], colnames=['Predicted'], margins=True)

    def predict_raster(self, targets, bbox, clf_name, region_key=None):
        """
        Export predicted raster.
        """
        name = self._get_raster_name(region_key)

        # Compute geotransform parameters for target rasters based on bbox and zoom.
        origin, width, height, scale = self._get_geotransform(bbox)

        predicted_raster = GDALRaster({
            'name': os.path.join(os.getcwd(), '{}-predicted-{}.tif'.format(name, clf_name)),
            'driver': 'tif',
            'datatype': 1,
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

        # Set data on predicted raster.
        predicted_raster.bands[0].data(result.reshape(predicted_raster.width, predicted_raster.height).astype('uint8'))

        print(predicted_raster.name)

        # Print raster to screen.
        plt.imshow(predicted_raster.bands[0].data())
        plt.show()
