from raster.models import RasterLayer
from raster_aggregation.exceptions import MissingQueryParameter
from raster_aggregation.models import AggregationLayer
from rest_framework import permissions

from django.http import Http404


class RasterTilePermission(permissions.BasePermission):
    """
    Checks if a user can request a tms or algebra tile.
    """

    def has_permission(self, request, view):
        # If no layers were requested, grant access.
        if not view.request.GET.get('layers', None):
            return True

        # Check user permissions only on non-public rasterlayers.
        qs = RasterLayer.objects.exclude(
            publicrasterlayer__public=True
        ).filter(
            id__in=view.get_ids().values()
        ).only('id').distinct()
        return all(request.user.has_perm('view_rasterlayer', lyr) for lyr in qs)


class ValueCountResultCreatePermission(permissions.BasePermission):
    """
    Checks if a user can create a value count result object.

    This permission only checks layer and aggregation area dependencies
    upon create (POST). All other cases are handled by the objec level
    permissions.

    The rationale for this is that the dependent objects are only needed
    on creation. The results are owned by the creator even if the layers
    or aggregation area permissions are unset.
    """
    def has_permission(self, request, view):
        # This check is for creation only.
        if request.method != 'POST':
            return True
        # The user can view all raster layers.
        # qs = RasterLayer.objects.filter(id__in=view.get_ids().values()).only('id').distinct()
        # view_all_rasters = all(request.user.has_perm('view_rasterlayer', lyr) for lyr in qs)
        view_all_rasters = True
        # Check for permission on aggregation area through aggregationlayer.
        aggarea_id = view.request.data.get('aggregationarea', None)
        # If not aggarea was provided, grant access (aggregation package will raise error later).
        if aggarea_id is None:
            return True
        agglyr = AggregationLayer.objects.get(aggregationarea=aggarea_id)
        view_agg = request.user.has_perm('view_aggregationlayer', agglyr)
        return view_all_rasters and view_agg


class TesseloObjectPermission(permissions.DjangoObjectPermissions):
    """
    Check if a user can see a raster layer.
    """
    perms_map = {
        'GET': ['%(app_label)s.view_%(model_name)s'],
        'OPTIONS': ['%(app_label)s.view_%(model_name)s'],
        'HEAD': ['%(app_label)s.view_%(model_name)s'],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }

    _public = False

    def has_permission(self, request, view):
        """
        Pass on global table level permissions, this permission class checks on
        the object level only.
        """
        return True

    def get_required_object_permissions(self, method, model_cls):
        # For public rasters, dont require object permissions.
        if self._public and method in permissions.SAFE_METHODS:
            return []
        return super().get_required_object_permissions(method, model_cls)

    def has_object_permission(self, request, view, obj):
        """
        Allow view for public rasters, otherwise handle with regular object permissions.
        """
        # Set public raster flag for object permission checking.
        self._public = hasattr(obj, 'public{0}'.format(view._model)) and getattr(obj, 'public{0}'.format(view._model)).public
        return super().has_object_permission(request, view, obj)


class ChangePermissionObjectPermission(permissions.DjangoObjectPermissions):
    """
    Check if a user can change permissions on an object. This assumes that only
    object managers can delete an object, so inviting additional people is
    limited to users that can manage the main object.
    """
    perms_map = {
        'GET': ['%(app_label)s.delete_%(model_name)s'],
        'POST': ['%(app_label)s.delete_%(model_name)s'],
    }

    def has_permission(self, request, view):
        """
        Pass on global table level permissions, this permission class checks on
        the object level only.
        """
        return True


class DependentObjectPermission(permissions.BasePermission):
    """
    Check if a user can change or delete a dependent object, based on the
    parent class.
    """

    def has_permission(self, request, view):
        """
        Pass on global table level permissions, this permission class checks on
        the object level only.
        """
        return True

    def has_object_permission(self, request, view, obj):
        """
        Allow change or delete for entries that belong to legends that the user
        can change.
        """
        parent = getattr(obj, view._parent_model.lower())

        # Raise 404 if user can not see parent object.
        if not request.user.has_perm('view_{0}'.format(view._parent_model.lower()), parent):
            raise Http404

        # Since user can see parent object, allow safe methods.
        if request.method in permissions.SAFE_METHODS:
            return True
        else:
            # Allow all other methods only if user can change the parent object.
            return request.user.has_perm('change_{0}'.format(view._parent_model.lower()), parent)


class AggregationAreaListPermission(permissions.BasePermission):
    """
    Checks if a user can request aggregation area list. For the individual
    object retrieval, the dependent object permission is used.
    """

    def has_permission(self, request, view):
        # For list requests (pk not provided), enforce filtering by one
        # aggregationlayer.
        if 'pk' not in view.kwargs and request.method == 'GET':
            if 'aggregationlayer' not in request.GET:
                raise MissingQueryParameter(detail='Missing query parameter: aggregationlayer')
            else:
                # Make sure the listed aggregation areas are from a layer where
                # the user has access permissions.
                try:
                    lyr = AggregationLayer.objects.get(id=request.query_params.get('aggregationlayer'))
                except AggregationLayer.DoesNotExist:
                    raise Http404

                if not request.user.has_perm('view_aggregationlayer', lyr):
                    raise Http404
        # For all other request allow access at the global level. The detail
        # permission is handled separately.
        return True
