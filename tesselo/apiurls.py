from rest_framework import routers

from formulary.views import FormulaViewSet
from raster_api.views import (
    AggregationAreaViewSet, AggregationLayerViewSet, AlgebraAPIView, ExportAPIView, LegendEntryViewSet,
    LegendSemanticsViewSet, LegendViewSet, RasterLayerViewSet, SentinelTileAggregationAreaViewSet,
    ValueCountResultViewSet, WorldLayerGroupViewSet, ZoneOfInterestViewSet, AggregationLayerVectorTilesViewSet,
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
router.register(
    r'vtiles/(?P<aggregationlayer>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>json|pbf)',
    AggregationLayerVectorTilesViewSet,
    base_name='vectortiles'
)

router.register(r'aggregationlayer', AggregationLayerViewSet)
router.register(r'aggregationarea', AggregationAreaViewSet)
router.register(r'valuecountresult', ValueCountResultViewSet)

router.register(r'worldlayergroup', WorldLayerGroupViewSet, base_name='worldlayergroup')
router.register(r'zoneofinterest', ZoneOfInterestViewSet, base_name='zoneofinterest')
router.register(r'sentineltileaggregationarea', SentinelTileAggregationAreaViewSet, base_name='sentineltileaggregationarea')
router.register(r'formula', FormulaViewSet, base_name='formula')
