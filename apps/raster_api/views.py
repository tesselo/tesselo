from __future__ import unicode_literals

import io
import json
import re
import zipfile
from datetime import datetime
from tempfile import NamedTemporaryFile

import numpy
from PIL import Image
from rest_framework import renderers, serializers
from rest_framework.generics import GenericAPIView
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ViewSet, ReadOnlyModelViewSet, GenericViewSet
from rest_framework.decorators import detail_route
from rest_framework.mixins import ListModelMixin

from django.conf import settings
from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos import Polygon
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.template.defaultfilters import slugify
from raster.algebra.const import ALGEBRA_PIXEL_TYPE_GDAL
from raster.algebra.parser import RasterAlgebraParser
from raster.const import EXPORT_MAX_PIXELS, IMG_FORMATS, MAX_EXPORT_NAME_LENGTH, README_TEMPLATE
from raster.exceptions import RasterAlgebraException
from raster.models import Legend, RasterLayer, RasterTile, LegendSemantics, LegendEntry
from raster.shortcuts import get_session_colormap
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import get_raster_tile, tile_bounds, tile_index_range, tile_scale
from raster.utils import band_data_to_image, colormap_to_rgba
from raster.views import RasterView, AlgebraView, TmsView, ExportView

from raster_api.serializers import LegendSerializer, LegendSemanticsSerializer, LegendEntrySerializer, RasterLayerSerializer


class RasterTileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RasterTile
        fields = ('id', 'tilez', 'tilex', 'tiley', 'rasterlayer')


class BinaryRenderer(renderers.BaseRenderer):
    media_type = '*/*'
    charset = None
    render_style = 'binary'

    def render(self, data, media_type=None, renderer_context=None):
        return data

class RasterAPIView(RasterView, ListModelMixin, GenericViewSet):

    renderer_classes = (BinaryRenderer, )
    queryset = RasterTile.objects.all()


class AlgebraAPIView(AlgebraView, RasterAPIView):
    """
    A view to calculate map algebra on raster layers.
    """

    def list(self, request, *args, **kwargs):
        return super(AlebraAPIView, self).get(*args, **kwargs)


class TmsAPIView(TmsView, RasterAPIView):

    def list(self, *args, **kwargs):
        """
        Returns an image rendered from a raster tile.
        """
        return super(TmsAPIView, self).get(*args, **kwargs)


class ExportAPIView(AlgebraView, RasterAPIView):

    def construct_raster(self, z, xmin, xmax, ymin, ymax):
        """
        Create an empty tif raster file on disk using the input tile range. The
        new raster aligns with the xyz tile scheme and can be filled
        sequentially with raster algebra results.
        """
        # Compute bounds and scale to construct raster.
        bounds = []
        for x in range(xmin, xmax + 1):
            for y in range(ymin, ymax + 1):
                bounds.append(tile_bounds(x, y, z))
        bounds = [
            min([bnd[0] for bnd in bounds]),
            min([bnd[1] for bnd in bounds]),
            max([bnd[2] for bnd in bounds]),
            max([bnd[3] for bnd in bounds]),
        ]
        scale = tile_scale(z)
        # Create tempfile.
        raster_workdir = getattr(settings, 'RASTER_WORKDIR', None)
        self.exportfile = NamedTemporaryFile(dir=raster_workdir, suffix='.tif')
        # Instantiate raster using the tempfile path.
        return GDALRaster({
            'srid': WEB_MERCATOR_SRID,
            'width': (xmax - xmin + 1) * WEB_MERCATOR_TILESIZE,
            'height': (ymax - ymin + 1) * WEB_MERCATOR_TILESIZE,
            'scale': (scale, -scale),
            'origin': (bounds[0], bounds[3]),
            'driver': 'tif',
            'bands': [{'data': [0], 'nodata_value': 0}],
            'name': self.exportfile.name,
            'datatype': ALGEBRA_PIXEL_TYPE_GDAL,
        })

    def get_tile_range(self):
        """
        Compute a xyz tile range from the query parameters. If no bbox
        parameter is found, the range defaults to the maximum extent of
        all input raster layers.
        """
        # Get raster layers
        layers = RasterLayer.objects.filter(id__in=self.get_ids().values())
        # Establish zoom level
        if self.request.GET.get('zoom', None):
            zlevel = int(self.request.GET.get('zoom'))
        else:
            # Get highest zoom level of all input layers
            zlevel = max([layer.metadata.max_zoom for layer in layers])
        # Use bounding box to compute tile range
        if self.request.GET.get('bbox', None):
            bbox = Polygon.from_bbox(self.request.GET.get('bbox').split(','))
            bbox.srid = 4326
            bbox.transform(WEB_MERCATOR_SRID)
            tile_range = tile_index_range(bbox.extent, zlevel)
        else:
            # Get list of tile ranges
            layer_ranges = []
            for layer in layers:
                layer_ranges.append(tile_index_range(layer.extent(), zlevel))
            # Estabish overlap of tile index ranges
            tile_range = [
                min([rng[0] for rng in layer_ranges]),
                min([rng[1] for rng in layer_ranges]),
                max([rng[2] for rng in layer_ranges]),
                max([rng[3] for rng in layer_ranges]),
            ]
        return [zlevel, ] + tile_range

    def write_colormap(self, zfile):
        # Try to get colormap
        colormap = self.get_colormap()
        # Set a simple header for this colormap
        colorstr = '# Raster Algebra Colormap\n'
        # Check if this is a continuous legend.
        colorstr += 'INTERPOLATION: ' + ('CONTINUOUS' if colormap.pop('continuous', None) else 'DISCRETE') + '\n'
        # Add expressions and colors of the colormap
        for key, val in colormap.items():
            colorstr += str(key) + ',' + ','.join((str(x) for x in val)) + ',' + str(key) + '\n'
        # Write colormap file
        zfile.writestr('COLORMAP.txt', colorstr)

    def write_readme(self, zfile):
        # Get tile index range
        zoom, xmin, ymin, xmax, ymax = self.get_tile_range()
        # Construct layer names string
        layerstr = ''
        for name, layerid in self.get_ids().items():
            layer = RasterLayer.objects.get(id=layerid)
            layerstr += '{layerid} "{name}" (Formula label: {label})\n'.format(
                name=layer.name,
                label=name,
                layerid=layerid
            )
        # Get description, append newline if provided
        description = self.request.GET.get('description', '')
        if description:
            description += '\n'
        # Initiate metadata object
        readmedata = {
            'datetime': datetime.now().strftime('%Y-%m-%d at %H:%M'),
            'url': self.request.build_absolute_uri(),
            'bbox': self.request.GET.get('bbox', 'Minimum bounding-box covering all layers.'),
            'formula': self.request.GET.get('formula'),
            'zoom': str(zoom),
            'xindexrange': '{} - {}'.format(xmin, xmax),
            'yindexrange': '{} - {}'.format(ymin, ymax),
            'layers': layerstr,
            'description': description,
        }
        # Write readme file
        readme = README_TEMPLATE.format(**readmedata)
        zfile.writestr('README.txt', readme)

    def list(self, request, *args, **kwargs):
        # Initiate algebra parser
        parser = RasterAlgebraParser()
        # Get formula from request
        formula = request.GET.get('formula')
        # Get id list from request
        ids = self.get_ids()
        # Compute tile index range
        zoom, xmin, ymin, xmax, ymax = self.get_tile_range()
        # Check maximum size of target raster in pixels
        max_pixels = getattr(settings, 'RASTER_EXPORT_MAX_PIXELS', EXPORT_MAX_PIXELS)
        if WEB_MERCATOR_TILESIZE * (xmax - xmin) * WEB_MERCATOR_TILESIZE * (ymax - ymin) > max_pixels:
            raise RasterAlgebraException('Export raster too large.')
        # Construct an empty raster with the output dimensions
        result_raster = self.construct_raster(zoom, xmin, xmax, ymin, ymax)
        target = result_raster.bands[0]
        # Get raster data as 1D arrays and store in dict that can be used
        # for formula evaluation.
        for xindex, x in enumerate(range(xmin, xmax + 1)):
            for yindex, y in enumerate(range(ymin, ymax + 1)):
                data = {}
                for name, layerid in ids.items():
                    tile = get_raster_tile(layerid, zoom, x, y)
                    if tile:
                        data[name] = tile
                # Ignore this tile if data is not found for all layers
                if len(data) != len(ids):
                    continue
                # Evaluate raster algebra expression, return 400 if not successful
                try:
                    # Evaluate raster algebra expression
                    tile_result = parser.evaluate_raster_algebra(data, formula)
                except:
                    raise RasterAlgebraException('Failed to evaluate raster algebra.')
                # Update nodata value on target
                target.nodata_value = tile_result.bands[0].nodata_value
                # Update results raster with algebra
                target.data(
                    data=tile_result.bands[0].data(),
                    size=(WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE),
                    offset=(xindex * WEB_MERCATOR_TILESIZE, yindex * WEB_MERCATOR_TILESIZE),
                )
        # Create filename base with datetime stamp
        filename_base = 'algebra_export'
        # Add name slug to filename if provided
        if request.GET.get('filename', ''):
            # Sluggify name
            slug = slugify(request.GET.get('filename'))
            # Remove all unwanted characters
            slug = "".join([c for c in slug if re.match(r'\w|\-', c)])
            # Limit length of custom name slug
            slug = slug[:MAX_EXPORT_NAME_LENGTH]
            # Add name slug to filename base
            filename_base += '_' + slug
        filename_base += '_{0}'.format(datetime.now().strftime('%Y_%m_%d_%H_%M'))
        # Compress resulting raster file into a zip archive
        raster_workdir = getattr(settings, 'RASTER_WORKDIR', None)
        dest = NamedTemporaryFile(dir=raster_workdir, suffix='.zip')
        dest_zip = zipfile.ZipFile(dest.name, 'w', allowZip64=True)
        dest_zip.write(
            filename=self.exportfile.name,
            arcname=filename_base + '.tif',
            compress_type=zipfile.ZIP_DEFLATED,
        )
        # Write README.txt and COLORMAP.txt files to zip file
        self.write_readme(dest_zip)
        self.write_colormap(dest_zip)
        # Close zip file before returning
        dest_zip.close()
        # Add header to trigger download in browser.
        headers = {'Content-Disposition': 'attachment; filename="{0}"'.format(filename_base + '.zip')}
        # Create file based response containing zip file and return for download
        return Response(
            open(dest.name, 'rb'),
            content_type='application/zip',
            headers=headers,
        )


class LegendView(RasterView):

    renderer_classes = (JSONRenderer, )

    def get(self, request, legend_id):
        """
        Returns the legend for this layer as a json string. The legend is a list of
        legend entries with the attributes "name", "expression" and "color".
        """
        if legend_id:
            # Get legend from id
            legend = get_object_or_404(Legend, id=legend_id)
        else:
            # Try to get legend from layer
            lyr = self.get_layer()
            if not lyr.legend:
                raise Http404
            legend = lyr.legend

        return Response(json.loads(legend.json), content_type='application/json')


class LegendViewSet(ModelViewSet):

    queryset = Legend.objects.all()
    serializer_class = LegendSerializer


class LegendEntryViewSet(ModelViewSet):

    queryset = LegendEntry.objects.all()
    serializer_class = LegendEntrySerializer


class LegendSemanticsViewSet(ModelViewSet):

    queryset = LegendSemantics.objects.all()
    serializer_class = LegendSemanticsSerializer


class RasterLayerViewSet(ModelViewSet):

    queryset = RasterLayer.objects.all()
    serializer_class = RasterLayerSerializer
