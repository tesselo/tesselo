from django_filters.rest_framework import DjangoFilterBackend
from raster.const import IMG_ENHANCEMENTS
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
    _layer = None

    @property
    def layer(self):
        if not self._layer:
            if self.kwargs['layer_type'] == 'scene':
                self._layer = get_object_or_404(SentinelTile, id=self.kwargs['layer_id'])
            else:
                self._layer = get_object_or_404(Composite, id=self.kwargs['layer_id'])

        return self._layer

    def get_ids(self):
        if not self._rasterlayer_lookup:
            # Construct lookup and simplify keys to match formula syntax
            # (B1 vs B01.jp2).
            lookup = {
                key.replace('.jp2', '').replace('0', ''): val for key, val in self.layer.rasterlayer_lookup.items()
            }
            if self.formula.rgb:
                # RGB mode expects a specific pattern for the band names.
                self._rasterlayer_lookup = {
                    'r': lookup['B4'],
                    'g': lookup['B3'],
                    'b': lookup['B2'],
                }
            else:
                # Only keep bands that are present in formula.
                self._rasterlayer_lookup = {key: val for key, val in lookup.items() if key in self.formula.formula}
            # Add predictelayer keys to lookup.
            for pred in self.formula.predictedlayerformula_set.all():
                self._rasterlayer_lookup[pred.key] = pred.predictedlayer.rasterlayer_id

        return self._rasterlayer_lookup

    _formula = None

    @property
    def formula(self):
        if not self._formula:
            self._formula = get_object_or_404(Formula, id=self.kwargs['formula_id'])
        return self._formula

    def get_formula(self):
        # Trigger RGB mode by returning None, otherwise return formula string.
        if not self.formula.rgb:
            return self.formula.formula

    def get_colormap(self, layer=None):
        return self.formula.colormap

    def enhance(self, img):
        # Enhancing only in RGB mode.
        if self.formula.rgb:
            for key, enhancer in IMG_ENHANCEMENTS.items():
                enhance_value = getattr(self.formula, 'rgb_' + key)
                if enhance_value:
                    img = enhancer(img).enhance(enhance_value)
        return img

    def get_alpha(self):
        return self.formula.rgb and self.formula.rgb_alpha

    def get_rgb_scale(self):
        # Scaling only in RGB mode.
        if self.formula.rgb:
            return self.formula.rgb_scale_min, self.formula.rgb_scale_max
