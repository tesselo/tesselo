from formulary.models import Formula
from formulary.serializers import FormulaSerializer
from raster_api.views import PermissionsModelViewSet


class FormulaViewSet(PermissionsModelViewSet):
    queryset = Formula.objects.all()
    serializer_class = FormulaSerializer
    _model = 'formula'
