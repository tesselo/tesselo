from __future__ import unicode_literals

from raster.models import Legend, LegendEntry, LegendSemantics, RasterLayer, RasterTile
from raster.views import AlgebraView, ExportView, RasterView
from rest_framework.filters import SearchFilter
from rest_framework.mixins import ListModelMixin
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from django.db.models import Q
from guardian.shortcuts import assign_perm
from raster_api.permissions import RasterLayerObjectPermission, RasterTilePermission
from raster_api.renderers import BinaryRenderer
from raster_api.serializers import (
    LegendEntrySerializer, LegendSemanticsSerializer, LegendSerializer, RasterLayerSerializer
)


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


class ExportAPIView(ExportView, RasterAPIView):

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
