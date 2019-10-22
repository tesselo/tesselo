from raster_aggregation.exceptions import MissingQueryParameter
from raster_aggregation.models import AggregationLayer
from rest_framework import permissions


class ReportAggregationPermission(permissions.BasePermission):
    """
    Checks if a user is allowed to render a formula based on the composite or
    scene that was requested.
    """
    def has_permission(self, request, view):
        # Skip this for detail requests, the detail case is handled in the get
        # object permission.
        if view.detail:
            return True

        aggarea_id = request.GET.get('aggregationarea', None)
        agglayer_id = request.GET.get('aggregationlayer', None)
        if aggarea_id:
            agglyr = AggregationLayer.objects.filter(aggregationarea=aggarea_id).first()
        elif agglayer_id:
            agglyr = AggregationLayer.objects.filter(id=agglayer_id).first()
        else:
            raise MissingQueryParameter(detail='Specify either aggregationlayer or aggregationarea filter.')

        if not request.user.has_perm('view_aggregationlayer', agglyr):
            return False

        return True

    def has_object_permission(self, request, view, obj):

        if obj.composite:
            composite_perm = request.user.has_perm('view_composite', obj.composite)
        else:
            composite_perm = True

        if obj.predictedlayer:
            predictedlayer_perm = request.user.has_perm('view_predictedlayer', obj.predictedlayer)
        else:
            predictedlayer_perm = True

        if obj.formula:
            formula_perm = request.user.has_perm('view_formula', obj.formula)
        else:
            formula_perm = True

        if obj.aggregationlayer:
            aggregationlayer_perm = request.user.has_perm('view_aggregationlayer', obj.aggregationlayer)
        else:
            aggregationlayer_perm = True

        return all([composite_perm, predictedlayer_perm, formula_perm, aggregationlayer_perm])
