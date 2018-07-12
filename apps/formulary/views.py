from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from formulary.models import Formula
from formulary.serializers import FormulaSerializer
from raster_api.views import PermissionsModelViewSet


class FormulaViewSet(PermissionsModelViewSet):
    queryset = Formula.objects.all().order_by('name')
    serializer_class = FormulaSerializer
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    search_fields = ('name', 'acronym')
    _model = 'formula'
