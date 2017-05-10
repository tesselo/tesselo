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
from rest_framework.filters import SearchFilter, DjangoObjectPermissionsFilter
from guardian.shortcuts import assign_perm
from django.db.models import Q
from guardian.shortcuts import get_objects_for_user

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
from raster.views import RasterView, AlgebraView, ExportView

from raster_api.serializers import LegendSerializer, LegendSemanticsSerializer, LegendEntrySerializer, RasterLayerSerializer
from raster_api.permissions import RasterTilePermission, RasterLayerObjectPermission
import warnings
from collections import defaultdict
from itertools import groupby

from django.apps import apps
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q, QuerySet
from django.shortcuts import _get_queryset

from guardian.compat import basestring, get_user_model, is_anonymous
from guardian.core import ObjectPermissionChecker
from guardian.ctypes import get_content_type
from guardian.exceptions import MixedContentTypeError, WrongAppError
from guardian.models import GroupObjectPermission
from guardian.utils import get_anonymous_user, get_group_obj_perms_model, get_identity, get_user_obj_perms_model

class BinaryRenderer(renderers.BaseRenderer):
    media_type = '*/*'
    charset = None
    render_style = 'binary'

    def render(self, data, media_type=None, renderer_context=None):
        return data


class RasterAPIView(RasterView, ListModelMixin, GenericViewSet):

    permission_classes = (RasterTilePermission, )
    renderer_classes = (BinaryRenderer, )
    queryset = RasterTile.objects.all()


class AlgebraAPIView(AlgebraView, RasterAPIView):
    """
    A view to calculate map algebra on raster layers.
    """

    def list(self, *args, **kwargs):
        return super(AlgebraAPIView, self).get(*args, **kwargs)


class ExportAPIView(AlgebraView, RasterAPIView):

    def list(self, request, *args, **kwargs):
        return super(ExportAPIView, self).get(*args, **kwargs)


class LegendViewSet(ModelViewSet):

    queryset = Legend.objects.all()
    serializer_class = LegendSerializer


class LegendEntryViewSet(ModelViewSet):

    queryset = LegendEntry.objects.all()
    serializer_class = LegendEntrySerializer


class LegendSemanticsViewSet(ModelViewSet):

    queryset = LegendSemantics.objects.all()
    serializer_class = LegendSemanticsSerializer
    filter_backends = (SearchFilter, )
    search_fields = ('name', 'description', 'keyword', )


class RasterLayerViewSet(ModelViewSet):

    queryset = RasterLayer.objects.all()
    serializer_class = RasterLayerSerializer
    permission_classes = (RasterLayerObjectPermission, )
    filter_backends = (SearchFilter, )
    search_fields = ('name', 'description', )

    def get_queryset(self):
        """
        A queryset with public layers or rasterlayers for which the user has
        direct view permissions.
        """
        qs = RasterLayer.objects.all()

        if not self.request.user.is_superuser:
            qs = qs.filter(
                (Q(rasterlayeruserobjectpermission__permission__codename='view_rasterlayer') & Q(rasterlayeruserobjectpermission__user=self.request.user)) |
                (Q(rasterlayergroupobjectpermission__permission__codename='view_rasterlayer') & Q(rasterlayergroupobjectpermission__group__in=self.request.user.groups.all())) |
                Q(publicrasterlayer__public=True)
            )

        return qs.order_by('id')

    def perform_create(self, serializer):
        # Create layer with default create function.
        layer = serializer.save()
        # Assign permissions for newly created layer.
        assign_perm('view_rasterlayer', self.request.user, layer)
        assign_perm('change_rasterlayer', self.request.user, layer)
        assign_perm('delete_rasterlayer', self.request.user, layer)
