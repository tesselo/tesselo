from __future__ import unicode_literals

from multiprocessing import Pool

from django_filters.rest_framework import DjangoFilterBackend
from guardian.shortcuts import assign_perm, get_groups_with_perms, get_users_with_perms, remove_perm
from raster.models import Legend, LegendEntry, LegendSemantics, RasterLayer, RasterTile
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import tile_bounds, tile_scale
from raster.views import AlgebraView, ExportView, RasterView
from raster_aggregation.models import AggregationArea, AggregationLayer, ValueCountResult
from raster_aggregation.serializers import AggregationAreaSimplifiedSerializer
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
from raster_api.filters import CompositeFilter, SentinelTileAggregationLayerFilter
from raster_api.permissions import (
    AggregationAreaListPermission, ChangePermissionObjectPermission, DependentObjectPermission, RasterObjectPermission,
    RasterTilePermission, ValueCountResultCreatePermission
)
from raster_api.renderers import BinaryRenderer
from raster_api.serializers import (
    AggregationLayerSerializer, CompositeSerializer, GroupSerializer, LegendEntrySerializer, LegendSemanticsSerializer,
    LegendSerializer, RasterLayerSerializer, SentinelTileAggregationLayerSerializer, UserSerializer,
    ValueCountResultSerializer, ZoneOfInterestSerializer
)
from raster_api.utils import EXPIRING_TOKEN_LIFESPAN
from sentinel.models import Composite, SentinelTileAggregationLayer, ZoneOfInterest


class RasterAPIView(RasterView, ListModelMixin, GenericViewSet):
    permission_classes = (IsAuthenticated, RasterTilePermission, )
    renderer_classes = (BinaryRenderer, )
    pagination_class = None
    queryset = RasterTile.objects.all()

    def dispatch(self, *args, **kwargs):
        response = super(RasterAPIView, self).dispatch(*args, **kwargs)
        response['Cache-Control'] = 'max-age=604800, private'  # 1 Week
        return response


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

    queryset = AggregationLayer.objects.all().order_by('name')
    serializer_class = AggregationLayerSerializer
    filter_backends = (SearchFilter, )
    search_fields = ('name', 'description', )

    _model = 'aggregationlayer'


class AggregationLayerVectorTilesViewSet(AggregationLayerVectorTilesViewSetOrig, PermissionsModelViewSet):

    serializer_class = Serializer

    _model = 'aggregationlayer'

    def dispatch(self, *args, **kwargs):
        response = super(AggregationLayerVectorTilesViewSet, self).dispatch(*args, **kwargs)
        response['Cache-Control'] = 'max-age=604800, private'  # 1 Week
        return response


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


class LargeResultsSetPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500


class CompositeViewSet(PermissionsModelViewSet):

    queryset = Composite.objects.all().order_by('min_date')
    serializer_class = CompositeSerializer
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    filter_class = CompositeFilter
    search_fields = ('name', 'description', )
    pagination_class = LargeResultsSetPagination

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


class SentinelTileAggregationLayerViewSet(ModelViewSet):
    serializer_class = SentinelTileAggregationLayerSerializer
    pagination_class = LargeResultsSetPagination
    permission_classes = (IsAuthenticated, DependentObjectPermission, AggregationAreaListPermission, )
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    filter_class = SentinelTileAggregationLayerFilter
    search_fields = ('sentineltile__prefix', )

    _parent_model = 'aggregationlayer'

    queryset = SentinelTileAggregationLayer.objects.all().order_by('id')


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
    # Compute bounds, scale and size of tile.
    bounds = tile_bounds(int(tilex), int(tiley), int(tilez))
    tilescale = tile_scale(int(tilez))

    # Open raster on s3.
    path = '/vsis3/{}'.format(prefix)
    rst = GDALRaster(path)

    # Warp parent tile to child tile in memory.
    target = rst.warp({
        'driver': 'MEM',
        'srid': WEB_MERCATOR_SRID,
        'width': WEB_MERCATOR_TILESIZE,
        'height': WEB_MERCATOR_TILESIZE,
        'scale': [tilescale, -tilescale],
        'origin': [bounds[0], bounds[3]],
    })

    # The GDALRaster can not be pickled, so it needs to be decomposed here.
    data = [{'data': band.data(), 'nodata_value': band.nodata_value} for band in target.bands]
    dtype = target.bands[0].datatype()

    return tilescale, dtype, (bounds[0], bounds[3]), data


class LambdaView(AlgebraView, RasterAPIView):
    """
    A view to calculate map algebra on raster layers.

    The format can be either png, jpg or tif.

    https://tesselo.com/api/sentinel/17/M/PT/2018/1/7/0/14/4554/8293.png?layers=r=1,b=2,g=3&scale=3,3e3&alpha

    https://tesselo.com/api/sentinel/17/M/PT/2018/1/7/0/14/4554/8293.png?layers=r=1,b=2,g=3&formula=(B04-B08)/(B04%2BB08)&colormap={"continuous":true,"range":[-1,1],"from":[165,0,38],"to":[0,104,55],"over":[249,247,174]}

    https://tesselo.com/api/landsat/c1/L8/011/062/LC08_L1TP_011062_20171013_20171024_01_T1/14/4554/8293.png?layers=r=1,b=2,g=3&scale=7e3,22e3&alpha

    https://tesselo.com/api/landsat/c1/L8/011/062/LC08_L1TP_011062_20171013_20171024_01_T1/14/4554/8293.png?layers=r=1,b=2,g=3&formula=(B4-B5)/(B4%2BB5)&colormap={"continuous":true,"range":[-1,1],"from":[165,0,38],"to":[0,104,55],"over":[249,247,174]}

    https://tesselo.com/api/naip/al/2015/1m/rgbir/30085/m_3008501_ne_16_1_20151014/17/34246/53654.png?layers=r=1,b=2,g=3&scale=0,255&alpha

    https://tesselo.com/api/naip/al/2015/1m/rgbir/30085/m_3008501_ne_16_1_20151014/17/34246/53654.png?layers=r=1,b=2&formula=(B4-B1)/(B1%2BB4)&colormap={"continuous":true,"range":[-1,1],"from":[165,0,38],"to":[0,104,55],"over":[249,247,174]}
    """
    permission_classes = (IsAuthenticated, )

    def get_ids(self):
        if 'sentinel' in self.kwargs:
            from sentinel.const import BAND_RESOLUTIONS
            bands = [bnd.split('.')[0] for bnd in BAND_RESOLUTIONS]
            if 'formula' in self.request.GET:
                return {band: band for band in bands if band in self.request.GET.get('formula')}
            else:
                return {
                    'r': 'B04',
                    'g': 'B03',
                    'b': 'B02',
                }
        elif 'landsat' in self.kwargs:
            if 'formula' in self.request.GET:
                bands = ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9', 'B10', 'B11']
                return {band: band for band in bands if band in self.request.GET.get('formula')}
            else:
                return {
                    'r': 'B4',
                    'g': 'B3',
                    'b': 'B2',
                }
        elif 'naip' in self.kwargs:
            if 'formula' in self.request.GET:
                bands = ['B1', 'B2', 'B3', 'B4']
                band_keys = {
                    'B1': 'B1:0',
                    'B2': 'B2:1',
                    'B3': 'B3:2',
                    'B4': 'B4:3',
                }
                return {band_keys[band]: 'RGBIR' for band in bands if band in self.request.GET.get('formula')}
            else:
                return {
                    'r:0': 'RGB',
                    'g:1': 'RGB',
                    'b:2': 'RGB',

                }

    def get_vsi_path(self):
        if 'sentinel' in self.kwargs:
            vsis3path = 'sentinel-s2-l1c/tiles/{utm_zone}/{lat_band}/{grid_id}/{year}/{month}/{day}/{scene_nr}/{{band}}.jp2'.format(
                utm_zone=self.kwargs.get('utm_zone'),
                lat_band=self.kwargs.get('lat_band'),
                grid_id=self.kwargs.get('grid_id'),
                year=self.kwargs.get('year'),
                month=self.kwargs.get('month'),
                day=self.kwargs.get('day'),
                scene_nr=self.kwargs.get('scene_nr'),
            )
        elif 'landsat' in self.kwargs:
            if 'collection' in self.kwargs:
                vsis3path = 'landsat-pds/{collection}/{sensor}/{row}/{column}/{scene}/{scene}_{{band}}.TIF'.format(
                    collection=self.kwargs.get('collection'),
                    sensor=self.kwargs.get('sensor'),
                    row=self.kwargs.get('row'),
                    column=self.kwargs.get('column'),
                    scene=self.kwargs.get('scene'),
                )
            else:
                vsis3path = 'landsat-pds/{sensor}/{row}/{column}/{scene}/{scene}_{{band}}.TIF'.format(
                    collection=self.kwargs.get('collection'),
                    sensor=self.kwargs.get('sensor'),
                    row=self.kwargs.get('row'),
                    column=self.kwargs.get('column'),
                    scene=self.kwargs.get('scene'),

                )
        elif 'naip' in self.kwargs:
                vsis3path = 'aws-naip/{state}/{year}/{resolution}/{img_src}/{quadrangle}/{scene}.tif'.format(
                    state=self.kwargs.get('state'),
                    year=self.kwargs.get('year'),
                    resolution=self.kwargs.get('resolution'),
                    img_src=self.kwargs.get('img_src'),
                    quadrangle=self.kwargs.get('quadrangle'),
                    scene=self.kwargs.get('scene'),
                )

        return vsis3path

    def list(self, request, *args, **kwargs):
        # Get layer ids
        ids = self.get_ids()

        # Get tile indices from the request url parameters.
        tilez = int(self.kwargs.get('z'))
        tilex = int(self.kwargs.get('x'))
        tiley = int(self.kwargs.get('y'))

        # VSIS3 path
        vsis3path = self.get_vsi_path()

        # Prepare unique list of layer ids to be efficient if the same layer
        # is used multiple times (for band access for instance).
        layerids = set(ids.values())

        # Construct pool arguments.
        pool_args = [(vsis3path.format(band=band_name), tilez, tilex, tiley) for band_name in layerids]

        # Get the tiles for each unique layer in parallel.
        with Pool(len(pool_args)) as pool:
            tile_results = pool.starmap(get_tile, pool_args)

        # Reconstruct raster objects from pooled data.
        tile_results = [GDALRaster({
            'driver': 'MEM',
            'srid': WEB_MERCATOR_SRID,
            'width': WEB_MERCATOR_TILESIZE,
            'height': WEB_MERCATOR_TILESIZE,
            'scale': [scale, -scale],
            'origin': origin,
            'datatype': dtype,
            'bands': data,
        }) for scale, dtype, origin, data in tile_results]

        # Construct tiles dict.
        tiles = dict(zip(layerids, tile_results))

        # Map tiles to a dict with formula names as keys.
        data = {}
        for name, layerid in ids.items():
            data[name] = tiles[layerid]

        formula = request.GET.get('formula', None)

        # Dispatch by request type. If a formula was provided, use raster
        # algebra otherwise look for rgb request.
        if formula:
            return self.get_algebra(data, formula)
        else:
            return self.get_rgb(data)
