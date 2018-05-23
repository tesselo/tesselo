import numpy
from django_filters.rest_framework import DjangoFilterBackend
from PIL import Image
from raster.tiles.lookup import get_raster_tile
from raster.views import RasterView
from rest_framework.decorators import detail_route
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_400_BAD_REQUEST
from rest_framework.viewsets import ReadOnlyModelViewSet

from django.http import Http404
from django.shortcuts import get_object_or_404
from raster_api.permissions import ChangePermissionObjectPermission, DependentObjectPermission
from raster_api.views import PermissionsModelViewSet
from sentinel import clouds, ecs
from sentinel.filters import SentinelTileFilter
from sentinel.models import CompositeBuild, CompositeTile, SentinelTile
from sentinel.serializers import CompositeBuildSerializer, CompositeTileSerializer, SentinelTileSerializer


class SentinelTilePageNumberPagination(PageNumberPagination):
    page_size = 100


class SentinelTileViewSet(ReadOnlyModelViewSet):

    permission_classes = (IsAuthenticated, )
    serializer_class = SentinelTileSerializer
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    pagination_class = SentinelTilePageNumberPagination
    search_fields = ('prefix', )
    filter_class = SentinelTileFilter

    def get_queryset(self):
        return SentinelTile.objects.all().order_by('id')


class CloudView(RasterView):

    def get(self, request, stile, z, x, y, **kwargs):

        scene = get_object_or_404(SentinelTile, pk=stile)

        stack = {}
        for band in scene.sentineltileband_set.all():
            tile = get_raster_tile(
                layer_id=band.layer_id,
                tilez=int(z),
                tilex=int(x),
                tiley=int(y),
            )
            if not tile:
                raise Http404('Tile not found.')
            stack[band.band] = tile.bands[0].data()

        # Compute cloud confidence mask.
        cloud_probs = clouds.clouds_v4(stack)

        # Reshape and rescale probabilities to png value range.
        size = 256 * 256
        cloud_probs = cloud_probs.flatten() * 255
        cloud_probs = cloud_probs.repeat(3).reshape((size, 3))

        # Create array of ones for alpha channel.
        alpha = numpy.ones((size, 1)) * 255

        # Create rgba matrix.
        rgba = numpy.append(cloud_probs, alpha, axis=1)

        # Reshape array to image size
        rgba = rgba.reshape(256, 256, 4)

        # Create image from array
        img = Image.fromarray(rgba.astype('uint8'))

        return self.write_img_to_response(img, {})


class CompositeBuildViewSet(PermissionsModelViewSet):

    serializer_class = CompositeBuildSerializer
    filter_fields = ('composite', 'aggregationlayer', 'status', )

    _model = 'compositebuild'

    def get_queryset(self):
        return CompositeBuild.objects.all().order_by('id')

    @detail_route(methods=['post'], permission_classes=[IsAuthenticated, ChangePermissionObjectPermission])
    def build(self, request, pk):
        """
        Schedule a composite build task to build this composite.
        """
        # Get composite build object.
        cbuild = self.get_object()
        if cbuild.status in (CompositeBuild.PENDING, CompositeBuild.INGESTING_SCENES, CompositeBuild.BUILDING_TILES):
            return Response(
                {'error': 'Composite Build is already in process. Wait until build finishes before triggering a new build.'},
                status=HTTP_400_BAD_REQUEST,
            )
        # Trigger build.
        cbuild.status = CompositeBuild.PENDING
        cbuild.save()
        ecs.composite_build_callback(cbuild.id, initiate=True, rebuild=True)

        return Response({'success': 'Triggered Composite Build {}'.format(cbuild.id)})


class CompositeTileViewSet(ReadOnlyModelViewSet):
    permission_classes = (IsAuthenticated, DependentObjectPermission)
    queryset = CompositeTile.objects.all().order_by('id')
    serializer_class = CompositeTileSerializer
    _parent_model = 'composite'

    @detail_route(methods=['post'], permission_classes=[IsAuthenticated, ChangePermissionObjectPermission])
    def build(self, request, pk):
        """
        Manually force a new composite tile build. Should only be necessary in
        special cases. Normally this happens automatically through the composite
        build object.
        """
        ctile = self.get_object()
        ctile.status = CompositeTile.PENDING
        ctile.save()
        ecs.process_compositetile(ctile.id)

        return Response({'success': 'Triggered Composite Tile Build {}'.format(ctile.id)})
