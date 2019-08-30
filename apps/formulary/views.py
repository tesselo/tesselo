from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from django.shortcuts import get_object_or_404
from formulary.models import Formula
from formulary.permissions import RenderFormulaPermission
from formulary.serializers import FormulaSerializer
from raster_api.views import AlgebraAPIView, PermissionsModelViewSet
from sentinel.models import Composite, SentinelTile


class FormulaViewSet(PermissionsModelViewSet):
    queryset = Formula.objects.all().order_by('name')
    serializer_class = FormulaSerializer
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    search_fields = ('name', 'acronym')
    _model = 'formula'


class FormulaAlgebraAPIView(AlgebraAPIView):

    permission_classes = PermissionsModelViewSet.permission_classes + (RenderFormulaPermission, )

    _rasterlayer_lookup = None

    def get_ids(self):
        if not self._rasterlayer_lookup:
            # Get DB object.
            if self.kwargs['layer_type'] == 'scene':
                layer = get_object_or_404(SentinelTile, id=self.kwargs['layer_id'])
            else:
                layer = get_object_or_404(Composite, id=self.kwargs['layer_id'])

            # Construct lookup and simplify keys to match formula syntax
            # (B1 vs B01.jp2).
            lookup = {
                key.replace('.jp2', '').replace('0', ''): val for key, val in layer.rasterlayer_lookup.items()
            }
            # Filter by formula content.
            self._rasterlayer_lookup = {key: val for key, val in lookup.items() if key in self.formula.formula}

        return self._rasterlayer_lookup

    _formula = None

    @property
    def formula(self):
        if not self._formula:
            self._formula = get_object_or_404(Formula, id=self.kwargs['formula_id'])
        return self._formula

    def get_formula(self):
        return self.formula.formula

    def get_colormap(self, layer=None):
        return self.formula.colormap
