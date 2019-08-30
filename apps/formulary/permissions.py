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
        # Get formula and layer object ids.
        formula_id = request.resolver_match.kwargs.get('formula_id')
        layer_id = request.resolver_match.kwargs.get('layer_id')
        # Check permissions.
        return all((
            request.user.has_perm(layer_perm, layer_id),
            request.user.has_perm('view_formula', formula_id),
        ))
