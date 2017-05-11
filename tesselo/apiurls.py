from rest_framework import routers

from raster_api.views import (
    AlgebraAPIView, ExportAPIView, LegendEntryViewSet, LegendSemanticsViewSet, LegendViewSet, RasterLayerViewSet
)

router = routers.DefaultRouter(trailing_slash=False)

router.register(r'rasterlayer', RasterLayerViewSet, base_name='rasterlayer')
router.register(r'legend', LegendViewSet)
router.register(r'legendsemantics', LegendSemanticsViewSet)
router.register(r'legendentry', LegendEntryViewSet)

router.register(
    r'tile/(?P<layer>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg)',
    AlgebraAPIView,
    base_name='tile'
)
router.register(
    r'algebra/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>jpg|png)',
    AlgebraAPIView,
    base_name='algebra'
)
router.register(
    r'export',
    ExportAPIView,
    base_name='export'
)
