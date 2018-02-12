from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from formulary.models import Formula, WMTSLayer
from formulary.serializers import FormulaSerializer, WMTSLayerSerializer
from raster_api.views import PermissionsModelViewSet


class FormulaViewSet(PermissionsModelViewSet):
    queryset = Formula.objects.all().order_by('name')
    serializer_class = FormulaSerializer
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    search_fields = ('name', 'acronym')
    _model = 'formula'


class WMTSLayerViewSet(PermissionsModelViewSet):
    queryset = WMTSLayer.objects.all()
    serializer_class = WMTSLayerSerializer
    _model = 'wmtslayer'
