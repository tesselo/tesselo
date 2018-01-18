from __future__ import unicode_literals

from multiprocessing import Pool

import numpy
from django_filters.rest_framework import DjangoFilterBackend
from guardian.shortcuts import assign_perm, get_groups_with_perms, get_users_with_perms, remove_perm
from PIL import Image
from raster.models import Legend, LegendEntry, LegendSemantics, RasterLayer, RasterTile
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import tile_bounds, tile_scale
from raster.views import AlgebraView, ExportView, RasterView
from raster_aggregation.models import AggregationArea, AggregationLayer, ValueCountResult
from raster_aggregation.serializers import (
    AggregationAreaSimplifiedSerializer, AggregationLayerSerializer, ValueCountResultSerializer
)
from raster_aggregation.views import AggregationLayerVectorTilesViewSet as AggregationLayerVectorTilesViewSetOrig
from raster_aggregation.views import ValueCountResultViewSet as ValueCountResultViewSetOrig
from rest_framework import renderers
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import detail_route
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.mixins import DestroyModelMixin, ListModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.status import HTTP_204_NO_CONTENT
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from django.contrib.auth.models import Group, User
from django.contrib.gis.gdal import GDALRaster
from django.db.models import Q
from django.shortcuts import get_object_or_404
from raster_api.permissions import (
    AggregationAreaListPermission, ChangePermissionObjectPermission, DependentObjectPermission, RasterObjectPermission,
    RasterTilePermission, ValueCountResultCreatePermission
)
from raster_api.renderers import BinaryRenderer
from raster_api.serializers import (
    CompositeSerializer, GroupSerializer, LegendEntrySerializer, LegendSemanticsSerializer, LegendSerializer,
    RasterLayerSerializer, SentinelTileAggregationLayerSerializer, UserSerializer, ZoneOfInterestSerializer
)
from raster_api.utils import EXPIRING_TOKEN_LIFESPAN
from sentinel.models import Composite, SentinelTileAggregationLayer, ZoneOfInterest


class RasterAPIView(RasterView, ListModelMixin, GenericViewSet):
    permission_classes = (IsAuthenticated, RasterTilePermission, )
    renderer_classes = (BinaryRenderer, )
    pagination_class = None
    queryset = RasterTile.objects.all()


class AlgebraAPIView(AlgebraView, RasterAPIView):
    """
    A view to calculate map algebra on raster layers.

    The format can be either png, jpg or tif.
    """

    def list(self, *args, **kwargs):
        return super(AlgebraAPIView, self).get(*args, **kwargs)


class ExportAPIView(ExportView, RasterAPIView):

    def list(self, request, *args, **kwargs):
        return super(ExportAPIView, self).get(*args, **kwargs)


class PermissionsModelViewSet(ModelViewSet):

    permission_classes = (IsAuthenticated, RasterObjectPermission)

    def get_queryset(self):
        """
        A queryset with public layers or rasterlayers for which the user has
        direct view permissions.
        """
        qs = self.queryset

        if not self.request.user.is_superuser:
            # Construct query object to check for user permissions.
            query_obj_codename = {'{0}userobjectpermission__permission__codename'.format(self._model): 'view_{0}'.format(self._model)}
            query_user_match = {'{0}userobjectpermission__user'.format(self._model): self.request.user}
            has_user_permission = Q(**query_obj_codename) & Q(**query_user_match)

            # Construct query object to check for group permissions.
            query_obj_codename = {'{0}groupobjectpermission__permission__codename'.format(self._model): 'view_{0}'.format(self._model)}
            query_group_match = {'{0}groupobjectpermission__group__in'.format(self._model): self.request.user.groups.all()}
            has_group_permission = Q(**query_obj_codename) & Q(**query_group_match)

            # Query object for public layers.
            query_public = {'public{0}__public'.format(self._model): True}
            is_public_obj = Q(**query_public)

            # Filter queryset.
            qs = qs.filter(has_user_permission | has_group_permission | is_public_obj)

        return qs.distinct().order_by('id')

    def _assign_perms(self, obj, model=None):
        if not model:
            model = self._model
        # Assign permissions for newly created object.
        assign_perm('view_{0}'.format(model), self.request.user, obj)
        assign_perm('change_{0}'.format(model), self.request.user, obj)
        assign_perm('delete_{0}'.format(model), self.request.user, obj)

    def perform_create(self, serializer):
        # Create object with default create function.
        obj = serializer.save()
        self._assign_perms(obj)

    def perform_destroy(self, instance):
        if getattr(instance, 'public{0}'.format(self._model.lower())).public:
            raise PermissionDenied('Public objects can not be deleted.')
        super(PermissionsModelViewSet, self).perform_destroy(instance)

    @detail_route(methods=['get', 'post'], url_name='invite', url_path='(?P<action>invite|exclude)/(?P<model>user|group)/(?P<permission>view|change|delete)/(?P<invitee>[0-9]+)', permission_classes=[IsAuthenticated, ChangePermissionObjectPermission])
    def invite(self, request, pk, action, model, permission, invitee):
        """
        Invite or exclude users and groups from having view, change, or delete
        permissions on this object.
        """
        if model == 'user':
            invitee = get_object_or_404(User, id=invitee)
        else:
            invitee = get_object_or_404(Group, id=invitee)

        obj = self.get_object()

        funk = assign_perm if action == 'invite' else remove_perm

        funk('{perm}_{model}'.format(perm=permission, model=self._model), invitee, obj)

        # Handle compositeband case.
        if self._model == 'composite':
            for wlayer in obj.compositebands.all():
                funk('{perm}_rasterlayer'.format(perm=permission), invitee, wlayer.rasterlayer)

        return Response(status=HTTP_204_NO_CONTENT)

    @detail_route(methods=['get', 'post'], permission_classes=[IsAuthenticated, ChangePermissionObjectPermission])
    def publish(self, request, pk=None):
        """
        Publish this object.
        """
        obj = self.get_object()
        child = getattr(obj, 'public{0}'.format(self._model.lower()))
        child.public = not child.public
        child.save()

        # Handle compositeband case.
        if self._model == 'composite':
            for wlayer in obj.compositebands.all():
                child = wlayer.rasterlayer.publicrasterlayer
                child.public = not child.public
                child.save()
        return Response(status=HTTP_204_NO_CONTENT)

    @detail_route(methods=['get'])
    def groups(self, request, pk=None):
        """
        List groups with permissions on this object.
        """
        obj = self.get_object()
        serializer = GroupSerializer(get_groups_with_perms(obj), many=True)
        return Response(serializer.data)

    @detail_route(methods=['get'])
    def users(self, request, pk=None):
        """
        List users with permissions on this object.
        """
        obj = self.get_object()
        serializer = UserSerializer(get_users_with_perms(obj), many=True)
        return Response(serializer.data)


class LegendViewSet(PermissionsModelViewSet):

    queryset = Legend.objects.all().order_by('id')
    serializer_class = LegendSerializer

    _model = 'legend'


class LegendEntryViewSet(RetrieveModelMixin,
                         UpdateModelMixin,
                         DestroyModelMixin,
                         GenericViewSet):
    permission_classes = (IsAuthenticated, DependentObjectPermission)
    queryset = LegendEntry.objects.all().order_by('id')
    serializer_class = LegendEntrySerializer

    _parent_model = 'legend'


class LegendSemanticsViewSet(PermissionsModelViewSet):

    queryset = LegendSemantics.objects.all().order_by('id')
    serializer_class = LegendSemanticsSerializer
    filter_backends = (SearchFilter, )
    search_fields = ('name', 'description', 'keyword', )

    _model = 'legendsemantics'


class RasterLayerViewSet(PermissionsModelViewSet):

    queryset = RasterLayer.objects.all().order_by('id')
    serializer_class = RasterLayerSerializer
    filter_backends = (SearchFilter, )
    search_fields = ('name', 'description', )

    _model = 'rasterlayer'


class AggregationLayerViewSet(PermissionsModelViewSet):

    queryset = AggregationLayer.objects.all().order_by('id')
    serializer_class = AggregationLayerSerializer
    filter_backends = (SearchFilter, )
    search_fields = ('name', 'description', )

    _model = 'aggregationlayer'


class AggregationLayerVectorTilesViewSet(AggregationLayerVectorTilesViewSetOrig, PermissionsModelViewSet):

    serializer_class = Serializer

    _model = 'aggregationlayer'


class AggregationAreaViewSet(ModelViewSet):

    queryset = AggregationArea.objects.all().order_by('id')
    serializer_class = AggregationAreaSimplifiedSerializer
    permission_classes = (IsAuthenticated, DependentObjectPermission, AggregationAreaListPermission, )
    filter_fields = ('aggregationlayer', )

    _parent_model = 'aggregationlayer'


class ValueCountResultViewSet(ValueCountResultViewSetOrig, PermissionsModelViewSet):

    permission_classes = (
        IsAuthenticated,
        RasterObjectPermission,
        ValueCountResultCreatePermission,
    )
    queryset = ValueCountResult.objects.all().order_by('id')
    serializer_class = ValueCountResultSerializer

    _model = 'valuecountresult'

    def perform_create(self, serializer):
        # Call perform create from the value count result view.
        super(ValueCountResultViewSet, self).perform_create(serializer)
        # Manually assign permissions after object was created.
        self._assign_perms(serializer.instance)

    def get_ids(self):
        return self.request.data.get('layer_names', {})


class CompositeViewSet(PermissionsModelViewSet):

    queryset = Composite.objects.all().order_by('id')
    serializer_class = CompositeSerializer
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    filter_fields = ('active', )
    search_fields = ('name', 'description', )

    _model = 'composite'

    def _assign_perms(self, obj):
        # Create permissions for the compositeband itself.
        super(CompositeViewSet, self)._assign_perms(obj)
        # Assign permissions to the dependent rasterlayers.
        for wlayer in obj.compositebands.all():
            super(CompositeViewSet, self)._assign_perms(wlayer.rasterlayer, 'rasterlayer')


class ZoneOfInterestViewSet(PermissionsModelViewSet):

    queryset = ZoneOfInterest.objects.all().order_by('id')
    serializer_class = ZoneOfInterestSerializer
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    filter_fields = ('active', 'composite')
    search_fields = ('name', )

    _model = 'zoneofinterest'


class STALPageNumberPagination(PageNumberPagination):
    page_size = 100


class SentinelTileAggregationLayerViewSet(PermissionsModelViewSet):
    serializer_class = SentinelTileAggregationLayerSerializer
    pagination_class = STALPageNumberPagination
    permission_classes = (IsAuthenticated, DependentObjectPermission, AggregationAreaListPermission, )
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    filter_fields = ('active', )
    search_fields = ('sentineltile__prefix', )

    _parent_model = 'aggregationlayer'

    def get_queryset(self):
        qs = SentinelTileAggregationLayer.objects.all().order_by('id')
        agglyr = self.request.GET.get('aggregationlayer', None)
        if agglyr:
            qs = qs.filter(aggregationlayer_id=agglyr)
        return qs


class ObtainExpiringAuthToken(ObtainAuthToken):
    """
    Obtain a fresh auth token by sending a unauthenticated POST request to this
    url with a username and password field. The tokens will be valid for 14
    days. Returns the token and its expiry date.
    """
    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                           context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, created = Token.objects.get_or_create(user=user)

        # Replace the token with a new one if there is an existing one.
        if not created:
            token.delete()
            token = Token.objects.create(user=user)

        return Response({
            'token': token.key,
            'expires': token.created + EXPIRING_TOKEN_LIFESPAN
        })


class RemoveAuthToken(APIView):
    """
    Destroy the current token of the user by sending an authenticated POST
    request to this url.
    """
    renderer_classes = (renderers.JSONRenderer,)

    def post(self, request, *args, **kwargs):
        Token.objects.filter(user=request.user).delete()
        return Response({'logout': 'Successfully logged out.'})


def get_tile(prefix, tilez, tilex, tiley):
    """
    Returns tile data for the given Sentinel-2 scene over the input TMS tile.
    """
    # Compute bounds, scale and size of tile
    bounds = tile_bounds(int(tilex), int(tiley), int(tilez))
    tilescale = tile_scale(int(tilez))

    # Open raster on s3
    path = '/vsis3/sentinel-s2-l1c/{}'.format(prefix)
    rst = GDALRaster(path)

    # Warp parent tile to child tile in memory.
    return rst.warp({
        'driver': 'MEM',
        'srid': WEB_MERCATOR_SRID,
        'width': WEB_MERCATOR_TILESIZE,
        'height': WEB_MERCATOR_TILESIZE,
        'scale': [tilescale, -tilescale],
        'origin': [bounds[0], bounds[3]],
    }).bands[0].data()


class LambdaView(RasterAPIView):

    def list(self, request, utm_zone, lat_band, grid_id, year, month, day, scene_nr, z, x, y, **kwargs):

        stile = 'tiles/{utm_zone}/{lat_band}/{grid_id}/{year}/{month}/{day}/{scene_nr}/'.format(
            utm_zone=utm_zone,
            lat_band=lat_band,
            grid_id=grid_id,
            year=year,
            month=month,
            day=day,
            scene_nr=scene_nr
        )

        red = get_tile(stile + 'B04.jp2', z, x, y)
        green = get_tile(stile + 'B03.jp2', z, x, y)
        blue = get_tile(stile + 'B02.jp2', z, x, y)

        # with Pool(3) as pool:
        #     red, green, blue = pool.starmap(get_tile, [
        #         (stile + 'B04.jp2', z, x, y),
        #         (stile + 'B03.jp2', z, x, y),
        #         (stile + 'B02.jp2', z, x, y),
        #     ])

        scale_min = 0.0
        scale_max = 3000.0

        # Clip the image minimum.
        red[red < scale_min] = scale_min
        green[green < scale_min] = scale_min
        blue[blue < scale_min] = scale_min

        # Clip the image maximum.
        red[red > scale_max] = scale_max
        green[green > scale_max] = scale_max
        blue[blue > scale_max] = scale_max

        # Scale the image.
        red = 255 * (red - scale_min) / scale_max
        green = 255 * (green - scale_min) / scale_max
        blue = 255 * (blue - scale_min) / scale_max

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
