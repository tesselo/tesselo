from __future__ import unicode_literals

from raster.models import Legend, LegendEntry, LegendSemantics, RasterLayer, RasterTile
from raster.views import AlgebraView, ExportView, RasterView
from rest_framework.decorators import detail_route
from rest_framework.filters import SearchFilter
from rest_framework.mixins import ListModelMixin
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet, ModelViewSet

from django.contrib.auth.models import Group, User
from django.db.models import Q
from django.http import Http404
from guardian.shortcuts import assign_perm, get_groups_with_perms, get_users_with_perms, remove_perm
from raster_api.permissions import ChangePermissionObjectPermission, RasterObjectPermission, RasterTilePermission
from raster_api.renderers import BinaryRenderer
from raster_api.serializers import (
    GroupSerializer, LegendEntrySerializer, LegendSemanticsSerializer, LegendSerializer, RasterLayerSerializer,
    UserSerializer
)


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

        return qs.order_by('id')

    def perform_create(self, serializer):
        # Create object with default create function.
        obj = serializer.save()
        # Assign permissions for newly created object.
        assign_perm('view_{0}'.format(self._model), self.request.user, obj)
        assign_perm('change_{0}'.format(self._model), self.request.user, obj)
        assign_perm('delete_{0}'.format(self._model), self.request.user, obj)

    @detail_route(methods=['get', 'post'], url_path='invite/(?P<invitee_id>[0-9]+)', permission_classes=[IsAuthenticated, ChangePermissionObjectPermission])
    def invite(self, request, pk, invitee_id, exclude=False):
        # Try to get either user or group.
        try:
            invitee = User.objects.get(id=invitee_id)
        except User.DoesNotExist:
            try:
                invitee = Group.objects.get(id=invitee_id)
            except Group.DoesNotExist:
                raise Http404

        obj = self.get_object()

        if exclude:
            remove_perm('view_{0}'.format(self._model), invitee, obj)
            remove_perm('change_{0}'.format(self._model), invitee, obj)
        else:
            assign_perm('view_{0}'.format(self._model), invitee, obj)
            assign_perm('change_{0}'.format(self._model), invitee, obj)

        return Response()

    @detail_route(methods=['get', 'post'], url_path='exclude/(?P<invitee_id>[0-9]+)', permission_classes=[IsAuthenticated, ChangePermissionObjectPermission])
    def exclude(self, request, pk, invitee_id):
        return self.invite(request, pk, invitee_id, exclude=True)

    @detail_route(methods=['get'])
    def groups(self, request, pk=None):
        obj = self.get_object()
        serializer = GroupSerializer(get_groups_with_perms(obj), many=True)
        return Response(serializer.data)

    @detail_route(methods=['get'])
    def users(self, request, pk=None):
        obj = self.get_object()
        serializer = UserSerializer(get_users_with_perms(obj), many=True)
        return Response(serializer.data)


class LegendViewSet(PermissionsModelViewSet):

    queryset = Legend.objects.all()
    serializer_class = LegendSerializer

    _model = 'legend'


class LegendEntryViewSet(ModelViewSet):

    queryset = LegendEntry.objects.all()
    serializer_class = LegendEntrySerializer


class LegendSemanticsViewSet(PermissionsModelViewSet):

    queryset = LegendSemantics.objects.all()
    serializer_class = LegendSemanticsSerializer
    filter_backends = (SearchFilter, )
    search_fields = ('name', 'description', 'keyword', )


class RasterLayerViewSet(PermissionsModelViewSet):

    queryset = RasterLayer.objects.all()
    serializer_class = RasterLayerSerializer
    filter_backends = (SearchFilter, )
    search_fields = ('name', 'description', )

    _model = 'rasterlayer'
