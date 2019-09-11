from rest_framework import permissions


class RenderFormulaPermission(permissions.BasePermission):
    """
    Checks if a user is allowed to render a formula based on the composite or
    scene that was requested.
    """
    def has_permission(self, request, view):
        # Reslove scene vs composite.
        layer_type = request.resolver_match.kwargs.get('layer_type')
        layer_perm = 'view_sentineltile' if layer_type == 'scene' else 'view_composite'
        # Check permissions.
        return all((
            request.user.has_perm(layer_perm, view.layer),
            request.user.has_perm('view_formula', view.formula),
        ))