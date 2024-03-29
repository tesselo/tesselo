import io

import boto3
from django.conf import settings
from django.contrib.auth.models import Group, User
from django.contrib.gis.db.models import Extent
from django.contrib.gis.gdal import GDALRaster
from django.contrib.gis.geos import Polygon
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from guardian.shortcuts import assign_perm, remove_perm
from raster.models import Legend, LegendEntry, LegendSemantics, RasterLayer
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import tile_bounds, tile_index_range, tile_scale
from raster.views import AlgebraView, ExportView, RasterView
from raster_aggregation.exceptions import DuplicateError
from raster_aggregation.models import AggregationArea, AggregationLayer, ValueCountResult
from raster_aggregation.serializers import AggregationAreaSerializer
from raster_aggregation.views import AggregationLayerVectorTilesViewSet as AggregationLayerVectorTilesViewSetOrig
from raster_aggregation.views import ValueCountResultViewSet as ValueCountResultViewSetOrig
from rest_framework import renderers
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.mixins import DestroyModelMixin, ListModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.views import APIView
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from jobs import ecs
from naip.models import NAIPQuadrangle
from naip.utils import get_naip_tile
from raster_api.const import COOKIE_AUTH_KEY, EXPIRING_TOKEN_LIFESPAN, NAIP_MIN_ZOOM
from raster_api.exceptions import MissingZoomLevel
from raster_api.filters import CompositeFilter, SentinelTileAggregationLayerFilter
from raster_api.models import ReadOnlyToken
from raster_api.permissions import (
    AggregationAreaListPermission, ChangePermissionObjectPermission, DependentObjectPermission, IsReadOnly,
    RasterTilePermission, TesseloObjectPermission, ValueCountResultPermission
)
from raster_api.renderers import BinaryRenderer
from raster_api.serializers import (
    AggregationLayerSerializer, CompositeSerializer, LegendEntrySerializer, LegendSemanticsSerializer,
    LegendSerializer, RasterLayerSerializer, ReadOnlyTokenSerializer, SentinelTileAggregationLayerSerializer,
    ValueCountResultSerializer
)
from raster_api.tasks import (
    aggregation_layer_parser_async, compute_single_value_count_result, compute_single_value_count_result_async
)
from raster_api.utils import get_empty_tile
from sentinel.clouds.inspect_composite import inspect_composite
from sentinel.models import Composite, SentinelTileAggregationLayer
from sentinel.utils import get_raster_tile


class ReadOnlyTokenViewSet(ModelViewSet):
    serializer_class = ReadOnlyTokenSerializer

    def get_queryset(self):
        return ReadOnlyToken.objects.filter(user=self.request.user)


class RasterAPIView(RasterView, ListModelMixin, GenericViewSet):
    permission_classes = (IsAuthenticated, IsReadOnly, RasterTilePermission, )
    renderer_classes = (BinaryRenderer, )
    pagination_class = None

    def dispatch(self, *args, **kwargs):
        response = super(RasterAPIView, self).dispatch(*args, **kwargs)
        response['Cache-Control'] = 'max-age=604800, private'  # 1 Week
        return response

    def get_tile(self, layer_id, zlevel=None):
        """
        Returns a tile for rendering. If the tile does not exists, higher
        level tiles are searched and warped to lower level if found.
        """
        if self.is_pixel_request:
            tilez = self.max_zoom
            # Derive the tile index from the input coordinates.
            xcoord = float(self.kwargs.get('xcoord'))
            ycoord = float(self.kwargs.get('ycoord'))
            bbox = [xcoord, ycoord, xcoord, ycoord]
            indexrange = tile_index_range(bbox, tilez)
            tilex = indexrange[0]
            tiley = indexrange[1]
        else:
            # Get tile indices from the request url parameters.
            tilez = int(self.kwargs.get('z'))
            tilex = int(self.kwargs.get('x'))
            tiley = int(self.kwargs.get('y'))

        return get_raster_tile(layer_id, tilez, tilex, tiley)


class AlgebraAPIView(AlgebraView, RasterAPIView):
    """
    A view to calculate map algebra on raster layers.

    The format can be either png, jpg or tif.
    """

    def list(self, *args, **kwargs):
        return super(AlgebraAPIView, self).get(*args, **kwargs)


class AdminAlgebraAPIView(AlgebraAPIView):
    permission_classes = (IsAdminUser, )


class ExportAPIView(ExportView, RasterAPIView):

    permission_classes = (IsAdminUser, )

    def list(self, *args, **kwargs):
        return super(ExportAPIView, self).get(*args, **kwargs)


class PermissionsModelViewSet(ModelViewSet):

    permission_classes = (IsAuthenticated, IsReadOnly, TesseloObjectPermission)

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

        return qs.distinct()

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

    @action(detail=True, methods=['get', 'post'], url_name='invite', url_path='(?P<action>invite|exclude)/(?P<model>user|group)/(?P<permission>view|change|delete)/(?P<invitee>[0-9]+)', permission_classes=[IsAuthenticated, IsReadOnly, ChangePermissionObjectPermission])
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

        return Response('{}d {} {} to {} {} {}'.format(action, model, invitee.id, permission, self._model, obj.id))

    @action(detail=True, methods=['get', 'post'], permission_classes=[IsAuthenticated, IsReadOnly, ChangePermissionObjectPermission])
    def publish(self, request, pk=None):
        """
        Publish this object.
        """
        obj = self.get_object()
        public_obj = getattr(obj, 'public{0}'.format(self._model.lower()))
        public_obj.public = not public_obj.public
        public_obj.save()
        # Handle compositeband case.

        if self._model == 'composite':
            for wlayer in obj.compositeband_set.all():
                child = wlayer.rasterlayer.publicrasterlayer
                child.public = not child.public
                child.save()
        return Response({'success': 'Made {} {} {}'.format(self._model, obj.id, 'public' if public_obj.public else 'private')})


class LegendViewSet(PermissionsModelViewSet):

    queryset = Legend.objects.all().order_by('id')
    serializer_class = LegendSerializer

    _model = 'legend'


class LegendEntryViewSet(RetrieveModelMixin,
                         UpdateModelMixin,
                         DestroyModelMixin,
                         GenericViewSet):
    permission_classes = (IsAuthenticated, IsReadOnly, DependentObjectPermission)
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

    @action(detail=True, methods=['post'])
    def upload(self, request, pk=None):
        """
        Returns signed upload link to replace current shape file.
        """
        if 'filename' not in request.data:
            raise ValueError('Provide the "filename" as post data.')

        # Generate S3 file key from filename and object id.
        filename = str(request.data.get('filename'))
        key = '{}/{}/{}'.format(AggregationLayer.shapefile.field.upload_to, pk, filename)

        # Generate presigned S3 upload url.
        s3 = boto3.client('s3')
        EXPIRES_IN_SECONDS = 300
        presigned_post = s3.generate_presigned_post(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME_MEDIA,
            Key=key,
            Fields={"Content-Type": 'multipart/form-data'},
            Conditions=[{"Content-Type": 'multipart/form-data'}],
            ExpiresIn=EXPIRES_IN_SECONDS,
        )

        return Response(presigned_post)

    @action(detail=True, methods=['post'])
    def parse(self, request, pk=None):
        """
        Parse an Aggregation Layer asynchronously.
        """
        # Ket S3 key from layer.
        key = AggregationLayer.objects.get(id=pk).shapefile.name
        s3 = boto3.client('s3')
        key_head = s3.head_object(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME_MEDIA,
            Key=key,
        )
        key_size = key_head['ContentLength']
        # Set lambda file size limit to 1MB.
        LAMBDA_SIZE_LIMIT_BYTES = 1e6
        # Parse large files on batch, the others in lambda.
        if key_size > LAMBDA_SIZE_LIMIT_BYTES:
            ecs.parse_aggregationlayer(pk)
        else:
            aggregation_layer_parser_async(pk)

        return Response('Triggered parsing for aggregation layer {}'.format(pk))

    @action(detail=True, methods=['post'])
    def update_extent(self, request, pk=None):
        """
        Update extent of this aggregation layer.
        """
        obj = self.get_object()
        extent = obj.aggregationarea_set.aggregate(Extent('geom'))['geom__extent']
        if extent:
            obj.extent = Polygon.from_bbox(extent)
            obj.save()
            msg = 'Updated extent of aggregationlayer.'
        else:
            msg = 'No polygons found, did not update extent.'

        return Response(msg)


class AggregationLayerVectorTilesViewSet(AggregationLayerVectorTilesViewSetOrig, PermissionsModelViewSet):

    serializer_class = Serializer

    _model = 'aggregationlayer'

    def dispatch(self, *args, **kwargs):
        response = super(AggregationLayerVectorTilesViewSet, self).dispatch(*args, **kwargs)
        response['Cache-Control'] = 'max-age=604800, private'  # 1 Week
        return response


class AggregationAreaViewSet(ModelViewSet):

    queryset = AggregationArea.objects.all().order_by('id')
    serializer_class = AggregationAreaSerializer
    permission_classes = (IsAuthenticated, IsReadOnly, DependentObjectPermission, AggregationAreaListPermission, )
    filter_fields = ('aggregationlayer', )

    _parent_model = 'aggregationlayer'


class ValueCountResultViewSet(ValueCountResultViewSetOrig):

    permission_classes = (IsAuthenticated, IsReadOnly, ValueCountResultPermission, )
    queryset = ValueCountResult.objects.all().order_by('id')
    serializer_class = ValueCountResultSerializer

    def perform_create(self, serializer):
        """
        A patched perform create, most of this code is a copy of the
        raster-aggregation package version, except for the value count task
        call, which was adopted to zappa tasks here.
        """
        # Get list of rasterlayers based on layer names dict.
        rasterlayers = [RasterLayer.objects.get(id=pk) for pk in set(serializer.validated_data.get('layer_names').values())]

        # Get zoom level, the serializer has a default to trick the validation. The
        # unique constraints on the model disable the required=False argument.
        if serializer.validated_data.get('zoom') != -1:
            zoom = serializer.validated_data.get('zoom')
        else:
            # Compute zoom if not provided. Work at the resolution of the
            # input layer with the highest zoom level by default, or the
            # lowest one if requested.
            zlevels = [rst.metadata.max_zoom for rst in rasterlayers]
            if 'minmaxzoom' in self.request.GET:
                # Get the minimum of maxzoom levels
                zoom = min(zlevels)
            elif 'maxzoom' in self.request.GET:
                # Limit maximum zoom level
                maxzoom = int(self.request.GET.get('maxzoom'))
                zoom = min(max(zlevels), maxzoom)
            else:
                # Compute at the maximum maxzoom (resolution of highest definition layer)
                zoom = max(zlevels)

        if zoom is None:
            raise MissingZoomLevel()

        # Create object with final zoom value.
        try:
            obj = serializer.save(zoom=zoom, rasterlayers=rasterlayers)
        except IntegrityError:
            raise DuplicateError()

        # Push value count task to queue.
        if 'synchronous' in self.request.GET:
            compute_single_value_count_result(obj.id)
            obj.refresh_from_db()
        else:
            compute_single_value_count_result_async(obj.id)

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
    search_fields = ('name', )
    pagination_class = LargeResultsSetPagination

    _model = 'composite'

    def _assign_perms(self, obj):
        # Create permissions for the compositeband itself.
        super(CompositeViewSet, self)._assign_perms(obj)
        # Assign permissions to the dependent rasterlayers.
        for wlayer in obj.compositeband_set.all():
            super(CompositeViewSet, self)._assign_perms(wlayer.rasterlayer, 'rasterlayer')

    @action(detail=True, methods=['get'])
    def inspect(self, request, pk=None):
        """
        Returns the RGB and SceneClass input to a specific composite tile.
        """
        # Get tile index from query params.
        tilez = int(self.request.query_params.get('tilez', None))
        tilex = int(self.request.query_params.get('tilex', None))
        tiley = int(self.request.query_params.get('tiley', None))
        # Check that all query params have been provided.
        if not tilez or not tilex or not tiley:
            return Response()
        # Construct inspection image.
        img = inspect_composite(pk, tilez, tilex, tiley)
        # Save image to io buffer.
        with io.BytesIO() as output:
            img.save(output, format='png')
            # Create response with image content.
            return HttpResponse(
                output.getvalue(),
                content_type='image/png',
            )


class SentinelTileAggregationLayerViewSet(ModelViewSet):
    serializer_class = SentinelTileAggregationLayerSerializer
    pagination_class = LargeResultsSetPagination
    permission_classes = (IsAuthenticated, IsReadOnly, DependentObjectPermission, AggregationAreaListPermission, )
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    filter_class = SentinelTileAggregationLayerFilter
    search_fields = ('sentineltile__prefix', )

    _parent_model = 'aggregationlayer'

    queryset = SentinelTileAggregationLayer.objects.all().select_related('sentineltile', 'sentineltile__mgrstile').order_by('id')


class ObtainExpiringAuthToken(ObtainAuthToken):
    """
    Obtain a fresh auth token by sending a unauthenticated POST request to this
    url with a username and password field. The tokens will be valid for 14
    days. Returns the token and its expiry date.
    """

    authentication_classes = []

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

        # Compute expiration date.
        expiration = token.created + EXPIRING_TOKEN_LIFESPAN

        # Obtain tesselo user account profile.
        if hasattr(user, 'tesselouseraccount'):
            profile = user.tesselouseraccount.profile
        else:
            profile = {}

        # Create reponse.
        response = Response({
            'token': token.key,
            'expires': expiration,
            'is_staff': user.is_staff,
            'profile': profile,
        })

        # Set token as cookie.
        response.set_cookie(
            COOKIE_AUTH_KEY,
            token,
            expires=expiration,
            httponly=True,
            domain=request.META.get('HTTP_HOST', None),
        )

        return response


class RemoveAuthToken(APIView):
    """
    Destroy the current token of the user by sending an authenticated POST
    request to this url.
    """
    renderer_classes = (renderers.JSONRenderer, )

    def post(self, request, *args, **kwargs):
        # Delete token from DB.
        Token.objects.filter(user=request.user).delete()
        # Create response
        response = Response({'logout': 'Successfully logged out.'})
        # Unset cookie.
        response.delete_cookie(
            COOKIE_AUTH_KEY,
            domain=request.META.get('HTTP_HOST', None),
        )

        return response


def get_tile(prefix, bounds, scale):
    """
    Returns tile data for the given Sentinel-2 scene over the input TMS tile.
    """
    # Open raster on s3.
    path = '/vsis3/{}'.format(prefix)
    rst = GDALRaster(path)

    # Warp parent tile to child tile in memory.
    target = rst.warp({
        'driver': 'MEM',
        'srid': WEB_MERCATOR_SRID,
        'width': WEB_MERCATOR_TILESIZE,
        'height': WEB_MERCATOR_TILESIZE,
        'scale': [scale, -scale],
        'origin': [bounds[0], bounds[3]],
    })

    # The GDALRaster can not be pickled, so it needs to be decomposed here.
    data = [{'data': band.data(), 'nodata_value': band.nodata_value} for band in target.bands]
    dtype = target.bands[0].datatype()

    return dtype, data


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
    permission_classes = (IsAuthenticated, IsReadOnly, )

    def get_ids(self):
        if 'sentinel' in self.kwargs or 'composite' in self.kwargs:
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
                # The RGBIR data is wrapped up in one multi band raster and will
                # be gotten anyway. So all bands can be added here without
                # filtering for formula values.
                return {
                    'B1': 'B1',
                    'B2': 'B2',
                    'B3': 'B3',
                    'B4': 'B4',
                }
            else:
                return {
                    'r': 'B1',
                    'g': 'B2',
                    'b': 'B3',
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
        elif 'composite' in self.kwargs:
            tilez = int(self.kwargs.get('z'))
            tilex = int(self.kwargs.get('x'))
            tiley = int(self.kwargs.get('y'))
            factor = tilez - 8
            if factor < 0:
                raise ValueError('Zoom level min 8')
            tilex = int(tilex / (2 ** factor))
            tiley = int(tiley / (2 ** factor))

            vsis3path = 'composite-single-task/8-{tilex}-{tiley}/{tilez}-{{band}}.tif'.format(
                tilex=tilex,
                tiley=tiley,
                tilez=tilez,
            )

        return vsis3path

    def list(self, request, *args, **kwargs):
        # Get layer ids
        ids = self.get_ids()

        # Prepare unique list of layer ids to be efficient if the same layer
        # is used multiple times (for band access for instance).
        layerids = sorted(set(ids.values()))

        # Get tile indices from the request url parameters.
        tilez = int(self.kwargs.get('z'))
        tilex = int(self.kwargs.get('x'))
        tiley = int(self.kwargs.get('y'))

        # Compute bounds, scale and size of tile.
        bounds = tile_bounds(int(tilex), int(tiley), int(tilez))
        origin = (bounds[0], bounds[3])
        scale = tile_scale(int(tilez))

        # Handle naip case.
        if 'naip' in self.kwargs and 'state' not in self.kwargs:
            # Limit access to high zoom levels.
            if tilez < NAIP_MIN_ZOOM:
                return self.write_img_to_response(get_empty_tile(tilez, NAIP_MIN_ZOOM), {})

            if 'formula' in self.request.GET:
                source = NAIPQuadrangle.RGBIR
            else:
                source = NAIPQuadrangle.RGB
            year = self.kwargs.get('year', None)
            tile_results = get_naip_tile(tilez, tilex, tiley, source, year)
            if not tile_results:
                return self.write_img_to_response(get_empty_tile(), {})
        else:
            # VSIS3 path
            vsis3path = self.get_vsi_path()
            # Get tile data.
            tile_results = [get_tile(vsis3path.format(band=band_name), bounds, scale) for band_name in layerids]

        # Reconstruct raster objects from data.
        tile_results = [GDALRaster({
            'driver': 'MEM',
            'srid': WEB_MERCATOR_SRID,
            'width': WEB_MERCATOR_TILESIZE,
            'height': WEB_MERCATOR_TILESIZE,
            'scale': [scale, -scale],
            'origin': origin,
            'datatype': dtype,
            'bands': data,
        }) for dtype, data in tile_results]

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
