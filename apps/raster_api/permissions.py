from rest_framework import permissions
from raster.models import RasterLayer

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
