from rest_framework import permissions


class RenderPredictedLayerPermission(permissions.BasePermission):
    """
    Checks if a user is allowed to render a formula based on the composite or
    scene that was requested.
    """
    def has_permission(self, request, view):
        return request.user.has_perm('view_predictedlayer', view.predictedlayer)
