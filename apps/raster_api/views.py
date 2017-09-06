from __future__ import unicode_literals

from django_filters.rest_framework import DjangoFilterBackend
from raster.models import Legend, LegendEntry, LegendSemantics, RasterLayer, RasterTile
from raster.views import AlgebraView, ExportView, RasterView
from rest_framework.decorators import detail_route
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter
from rest_framework.mixins import DestroyModelMixin, ListModelMixin, RetrieveModelMixin, UpdateModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_204_NO_CONTENT
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from django.contrib.auth.models import Group, User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from guardian.shortcuts import assign_perm, get_groups_with_perms, get_users_with_perms, remove_perm
from raster_aggregation.models import AggregationArea, AggregationLayer, ValueCountResult
from raster_aggregation.serializers import (
    AggregationAreaSimplifiedSerializer, AggregationLayerSerializer, ValueCountResultSerializer
)
from raster_aggregation.views import ValueCountResultViewSet as ValueCountResultViewSetOrig
from raster_api.permissions import (
    AggregationAreaListPermission, ChangePermissionObjectPermission, DependentObjectPermission, RasterObjectPermission,
    RasterTilePermission, ValueCountResultCreatePermission
)
from raster_api.renderers import BinaryRenderer
from raster_api.serializers import (
    GroupSerializer, LegendEntrySerializer, LegendSemanticsSerializer, LegendSerializer, RasterLayerSerializer,
    SentinelTileAggregationAreaSerializer, UserSerializer, WorldLayerGroupSerializer, ZoneOfInterestSerializer
)
from sentinel.models import SentinelTileAggregationArea, WorldLayerGroup, ZoneOfInterest


class RasterAPIView(RasterView, ListModelMixin, GenericViewSet):

    permission_classes = (IsAuthenticated, RasterTilePermission, )
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

        # Handle worldlayer case.
        if self._model == 'worldlayergroup':
            for wlayer in obj.worldlayers.all():
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

        # Handle worldlayer case.
        if self._model == 'worldlayergroup':
            for wlayer in obj.worldlayers.all():
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


class WorldLayerGroupViewSet(PermissionsModelViewSet):

    queryset = WorldLayerGroup.objects.all().order_by('id')
    serializer_class = WorldLayerGroupSerializer
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    filter_fields = ('active', )
    search_fields = ('name', 'description', )

    _model = 'worldlayergroup'

    def _assign_perms(self, obj):
        # Create permissions for the worldlayer itself.
        super(WorldLayerGroupViewSet, self)._assign_perms(obj)
        # Assign permissions to the dependent rasterlayers.
        for wlayer in obj.worldlayers.all():
            super(WorldLayerGroupViewSet, self)._assign_perms(wlayer.rasterlayer, 'rasterlayer')


class ZoneOfInterestViewSet(PermissionsModelViewSet):

    queryset = ZoneOfInterest.objects.all().order_by('id')
    serializer_class = ZoneOfInterestSerializer
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    filter_fields = ('active', 'worldlayergroup')
    search_fields = ('name', )

    _model = 'zoneofinterest'


class SentinelTileAggregationAreaViewSet(ModelViewSet):

    serializer_class = SentinelTileAggregationAreaSerializer
    permission_classes = (IsAuthenticated, DependentObjectPermission, )  # AggregationAreaListPermission, )

    _parent_model = 'aggregationlayer'

    def get_queryset(self):
        qs = SentinelTileAggregationArea.objects.all().order_by('id')
        agglyr = self.request.GET.get('aggregationlayer', None)
        if agglyr:
            qs = qs.filter(aggregationarea__aggregationlayer_id=agglyr)
        return qs
