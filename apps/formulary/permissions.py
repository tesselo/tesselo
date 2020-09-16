from rest_framework import permissions


class RenderFormulaPermission(permissions.BasePermission):
    """
    Checks if a user is allowed to render a formula based on the composite or
    scene that was requested.
    """
    def has_permission(self, request, view):
        # Reslove scene vs composite.
        layer_type = request.resolver_match.kwargs.get('layer_type')
        # Allow all users to see scenes, limit access to composites.
        if layer_type == 'scene':
            can_see_layer = True
        elif layer_type == 'composite':
            can_see_layer = request.user.has_perm('view_composite', view.layer)
        else:
            can_see_layer = True

        # Check formula permission.
        can_see_formula = request.user.has_perm('view_formula', view.formula)

        return can_see_layer and can_see_formula
