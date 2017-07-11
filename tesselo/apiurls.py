from rest_framework import routers

from raster_api.views import (
    AggregationAreaViewSet, AggregationLayerViewSet, AlgebraAPIView, ExportAPIView, LegendEntryViewSet,
    LegendSemanticsViewSet, LegendViewSet, RasterLayerViewSet, ValueCountResultViewSet, WorldLayerGroupViewSet,
    ZoneOfInterestViewSet
)

router = routers.DefaultRouter(trailing_slash=False)

router.register(r'rasterlayer', RasterLayerViewSet)
router.register(r'legend', LegendViewSet)
router.register(r'legendsemantics', LegendSemanticsViewSet)
router.register(r'legendentry', LegendEntryViewSet)

router.register(
    r'tile/(?P<layer>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    AlgebraAPIView,
    base_name='tile'
)
router.register(
    r'algebra/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>jpg|png|tif)',
    AlgebraAPIView,
    base_name='algebra'
)
router.register(
    r'export',
    ExportAPIView,
    base_name='export'
)

router.register(r'aggregationlayer', AggregationLayerViewSet)
router.register(r'aggregationarea', AggregationAreaViewSet)
router.register(r'valuecountresult', ValueCountResultViewSet)

router.register(r'worldlayergroup', WorldLayerGroupViewSet, base_name='worldlayergroup')
router.register(r'zoneofinterest', ZoneOfInterestViewSet, base_name='zoneofinterest')
