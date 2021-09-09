import json
import os
import uuid

import numpy
from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.gdal.raster.const import VSI_FILESYSTEM_BASE_PATH
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from PIL import Image
from raster.algebra.const import BAND_INDEX_SEPARATOR
from raster.algebra.parser import RasterAlgebraParser
from raster.const import IMG_ENHANCEMENTS, IMG_FORMATS
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.utils import band_data_to_image, pixel_value_from_point
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination

from formulary.models import Formula
from formulary.permissions import RenderFormulaPermission
from formulary.serializers import FormulaSerializer
from raster_api.views import AlgebraAPIView, PermissionsModelViewSet
from sentinel.models import Composite, SentinelTile
from sentinel_1 import const


class FormulaPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 500


class FormulaViewSet(PermissionsModelViewSet):
    queryset = Formula.objects.all().order_by('-rgb', 'name')
    serializer_class = FormulaSerializer
    pagination_class = FormulaPagination
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    search_fields = ('name', 'acronym')
    _model = 'formula'


class FormulaAlgebraAPIView(AlgebraAPIView):

    permission_classes = PermissionsModelViewSet.permission_classes + (RenderFormulaPermission, )

    _rasterlayer_lookup = {}
    _layer = None

    @property
    def layer(self):
        if not self._layer:
            # Get single composite if specified.
            if hasattr(self.formula, 'composite') and self.formula.composite:
                self._layer = self.formula.composite
            elif 'layer_type' in self.kwargs:
                # Get scene or composite ID from url.
                if self.kwargs['layer_type'] == 'scene':
                    self._layer = get_object_or_404(SentinelTile, id=self.kwargs['layer_id'])
                else:
                    self._layer = get_object_or_404(Composite, id=self.kwargs['layer_id'])
            else:
                raise ValueError('Could not determine layer.')

        return self._layer

    def get_ids(self):
        if not self._rasterlayer_lookup:
            # TODO: Rename the "discrete" field to be more legible.
            if not self.formula.discrete:
                # Construct lookup and simplify keys to match formula syntax
                # (B1 vs B01.jp2).
                lookup = {
                    key.replace('.jp2', '').replace('0', ''): val for key, val in self.layer.rasterlayer_lookup.items()
                }
            if self.formula.rgb:
                # RGB mode expects a specific pattern for the band names.
                if self.formula.rgb_platform == Formula.S1:
                    # Since these are decibel values, the difference of the two
                    # bands is equivalent to the log of the ratio.
                    self._rasterlayer_lookup = {
                        'r': lookup[const.BDVV],
                        'g': lookup[const.BDVH],
                        'b': lookup[const.BDVV],
                    }
                elif self.formula.rgb_platform == Formula.S2:
                    self._rasterlayer_lookup = {
                        'r': lookup['B4'],
                        'g': lookup['B3'],
                        'b': lookup['B2'],
                    }
                else:
                    raise ValueError('Unknown RGB platform {}.'.format(self.formula.rgb_platform))
            elif not self.formula.discrete:
                # Only keep bands that are present in formula.
                self._rasterlayer_lookup = {key: val for key, val in lookup.items() if key in self.formula.formula}

            # Add predictelayer keys to lookup.
            for pred in self.formula.predictedlayerformula_set.all():
                self._rasterlayer_lookup[pred.key] = pred.predictedlayer.rasterlayer_id

        return self._rasterlayer_lookup

    _formula = None

    @property
    def formula(self):
        if not self._formula:
            self._formula = get_object_or_404(Formula, id=self.kwargs['formula_id'])
        return self._formula

    def get_formula(self):
        # Trigger RGB mode by returning None, otherwise return formula string.
        if not self.formula.rgb:
            return self.formula.formula

    def get_colormap(self, layer=None):
        return self.formula.colormap

    def enhance(self, img):
        # Enhancing only in RGB mode.
        if self.formula.rgb:
            for key, enhancer in IMG_ENHANCEMENTS.items():
                enhance_value = getattr(self.formula, 'rgb_' + key)
                if enhance_value:
                    img = enhancer(img).enhance(enhance_value)
        return img

    def get_alpha(self):
        return self.formula.rgb and self.formula.rgb_alpha

    def get_rgb_scale(self):
        # Scaling only in RGB mode.
        if self.formula.rgb:
            return self.formula.rgb_scale_min, self.formula.rgb_scale_max

    def get_algebra(self, data, formula):
        """
        Patched directly from django-raster.
        """
        parser = RasterAlgebraParser()

        # Evaluate raster algebra expression.
        result = parser.evaluate_raster_algebra(data, formula)

        # For pixel value requests, return result as json.
        if self.is_pixel_request:
            xcoord = float(self.kwargs.get('xcoord'))
            ycoord = float(self.kwargs.get('ycoord'))
            val = pixel_value_from_point(result, [xcoord, ycoord])
            return HttpResponse(
                json.dumps({'x': xcoord, 'y': ycoord, 'value': val}),
                content_type='application/json',
            )

        # For tif requests, skip colormap and return georeferenced tif file.
        if self.kwargs.get('frmt') == 'tif':
            vsi_path = os.path.join(VSI_FILESYSTEM_BASE_PATH, str(uuid.uuid4()))
            rast = result.warp({
                'name': vsi_path,
                'driver': 'tif',
                'compress': 'DEFLATE',
            })
            content_type = IMG_FORMATS['tif'][1]
            return HttpResponse(rast.vsi_buffer, content_type)

        # Get array from algebra result
        if result.bands[0].nodata_value is None:
            result = result.bands[0].data()
        else:
            result = numpy.ma.masked_values(
                result.bands[0].data(),
                result.bands[0].nodata_value,
            )

        # Get colormap.
        colormap = self.get_colormap()

        # Render tile using the legend data
        img, stats = band_data_to_image(result, colormap)

        # Return rendered image
        return self.write_img_to_response(img, stats)

    def get_rgb(self, data):
        """
        Patched directly from django-raster.
        """
        # Get data arrays from tiles, by band if requested.
        for key, tile in data.items():

            keysplit = key.split(BAND_INDEX_SEPARATOR)
            variable = keysplit[0]

            if len(keysplit) > 1:
                band_index = int(keysplit[1])
            else:
                band_index = 0

            band = tile.bands[band_index]
            if variable == 'r':
                red = band.data()
                red_nodata = band.nodata_value
                red_gdal_dtype = band.datatype()
            elif variable == 'g':
                green = band.data()
                green_nodata = band.nodata_value
            elif variable == 'b':
                blue = band.data()
                blue_nodata = band.nodata_value

        # For tif requests, skip rgb rendering and return georeferenced tif file.
        if self.kwargs.get('frmt') == 'tif':
            vsi_path = os.path.join(VSI_FILESYSTEM_BASE_PATH, str(uuid.uuid4()))
            # Construct 3 band raster, assuming all
            ref = next(iter(data.values()))
            result = GDALRaster({
                'name': vsi_path,
                'driver': 'tif',
                'srid': WEB_MERCATOR_SRID,
                'datatype': red_gdal_dtype,
                'width': ref.width,
                'height': ref.height,
                'origin': ref.origin,
                'scale': ref.scale,
                'skew': ref.skew,
                'bands': [
                    {'data': red, 'nodata_value': red_nodata},
                    {'data': green.astype(red.dtype), 'nodata_value': green_nodata},
                    {'data': blue.astype(red.dtype), 'nodata_value': blue_nodata},
                ],
                'papsz_options': {
                    'compress': 'deflate',
                },
            })
            content_type = IMG_FORMATS['tif'][1]
            return HttpResponse(result.vsi_buffer, content_type)

        # Get scale for the image value range.
        scale = self.get_rgb_scale()
        if scale is not None:
            # Clip the image minimum.
            red[red < scale[0]] = scale[0]
            green[green < scale[0]] = scale[0]
            blue[blue < scale[0]] = scale[0]

            # Clip the image maximum.
            red[red > scale[1]] = scale[1]
            green[green > scale[1]] = scale[1]
            blue[blue > scale[1]] = scale[1]

            # Scale the image.
            red = 255 * (red - scale[0]) / scale[1]
            green = 255 * (green - scale[0]) / scale[1]
            blue = 255 * (blue - scale[0]) / scale[1]

        if self.get_alpha():
            mode = 'RGBA'
            reshape = 4
            # Create the alpha channel.
            alpha = 255 * (red > 0) * (blue > 0) * (green > 0)
            img_array = numpy.array((red.ravel(), green.ravel(), blue.ravel(), alpha.ravel()))
        else:
            mode = 'RGB'
            reshape = 3
            img_array = numpy.array((red.ravel(), green.ravel(), blue.ravel()))

        # Reshape array into tile size.
        img_array = img_array.T.reshape(WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE, reshape).astype('uint8')

        # Create image from array
        img = Image.fromarray(img_array, mode=mode)
        stats = {}

        # Return rendered image
        return self.write_img_to_response(img, stats)
