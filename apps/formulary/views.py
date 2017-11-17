from formulary.models import Formula, WMTSLayer
from formulary.serializers import FormulaSerializer, WMTSLayerSerializer
from raster_api.views import PermissionsModelViewSet


class FormulaViewSet(PermissionsModelViewSet):
    queryset = Formula.objects.all()
    serializer_class = FormulaSerializer
    _model = 'formula'


class WMTSLayerViewSet(PermissionsModelViewSet):
    queryset = WMTSLayer.objects.all()
    serializer_class = WMTSLayerSerializer
    _model = 'wmtslayer'
