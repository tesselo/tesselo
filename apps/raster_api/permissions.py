from raster.models import RasterLayer
from rest_framework import permissions


class RasterTilePermission(permissions.BasePermission):
    """
    Checks if a user can request a tms or algebra tile.
    """

    def has_permission(self, request, view):
        if 'layer' in view.kwargs:
            qs = RasterLayer.objects.filter(id=view.kwargs.get('layer'))
        else:
            qs = RasterLayer.objects.filter(id__in=view.get_ids().values())

        return all(request.user.has_perm('view_rasterlayer', lyr) for lyr in qs)


class RasterLayerObjectPermission(permissions.DjangoObjectPermissions):
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

    def get_required_object_permissions(self, method, model_cls):
        # For public rasters, dont require object permissions.
        if self._public and method in permissions.SAFE_METHODS:
            return []
        return super(RasterLayerObjectPermission, self).get_required_object_permissions(method, model_cls)

    def has_object_permission(self, request, view, obj):
        """
        Allow view for public rasters, otherwise handle with regular object permissions.
        """
        # Set public raster flag for object permission checking.
        self._public = hasattr(obj, 'publicrasterlayer') and obj.publicrasterlayer.public

        return super(RasterLayerObjectPermission, self).has_object_permission(request, view, obj)
