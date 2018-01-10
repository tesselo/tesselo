from rest_framework import routers

from django.conf.urls import include, url
from formulary.views import FormulaViewSet, WMTSLayerViewSet
from formulary.wmts import WMTSAPIView
from raster_api.views import (
    AggregationAreaViewSet, AggregationLayerVectorTilesViewSet, AggregationLayerViewSet, AlgebraAPIView,
    CompositeViewSet, ExportAPIView, LegendEntryViewSet, LegendSemanticsViewSet, LegendViewSet,
    ObtainExpiringAuthToken, RasterLayerViewSet, RemoveAuthToken, SentinelTileAggregationLayerViewSet,
    ValueCountResultViewSet, ZoneOfInterestViewSet
)
from sentinel.views import SentinelTileViewSet

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
    r'^pixel/(?P<xcoord>-?\d+(?:\.\d+)?)/(?P<ycoord>-?\d+(?:\.\d+)?)$',
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

router.register(r'composite', CompositeViewSet, base_name='composite')
router.register(r'zoneofinterest', ZoneOfInterestViewSet, base_name='zoneofinterest')
router.register(r'sentineltileaggregationlayer', SentinelTileAggregationLayerViewSet, base_name='sentineltileaggregationlayer')
router.register(r'sentineltile', SentinelTileViewSet, base_name='sentineltile')

router.register(r'formula', FormulaViewSet, base_name='formula')
router.register(r'wmtslayer', WMTSLayerViewSet, base_name='wmtslayer')


apiurlpatterns = [
    url(r'^api/token-auth/', ObtainExpiringAuthToken.as_view()),
    url(r'^api/token-logout/', RemoveAuthToken.as_view()),
    url(r'^api/wmts$', WMTSAPIView.as_view()),
    url(r'^api/', include(router.urls)),
]
