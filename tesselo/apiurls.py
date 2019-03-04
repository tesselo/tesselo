from rest_framework import routers

from classify.views import ClassifierViewSet, PredictedLayerViewSet, TrainingLayerViewSet, TrainingSampleViewSet
from django.conf.urls import include, url
from django.views.decorators.csrf import csrf_exempt
from formulary.views import FormulaViewSet
from raster_api.views import (
    AggregationAreaViewSet, AggregationLayerVectorTilesViewSet, AggregationLayerViewSet, AlgebraAPIView,
    CompositeViewSet, ExportAPIView, GroupViewSet, LambdaView, LegendEntryViewSet, LegendSemanticsViewSet,
    LegendViewSet, ObtainExpiringAuthToken, RasterLayerViewSet, ReadOnlyTokenViewSet, RemoveAuthToken,
    SentinelTileAggregationLayerViewSet, UserViewSet, ValueCountResultViewSet
)
from sentinel.views import CompositeBuildViewSet, CompositeTileViewSet, SentinelTileViewSet
from wmts.views import WMTSAPIView, WMTSLayerViewSet

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
router.register(
    r'(?P<sentinel>sentinel)/(?P<utm_zone>[^/]+)/(?P<lat_band>[^/]+)/(?P<grid_id>[^/]+)/(?P<year>[^/]+)/(?P<month>[^/]+)/(?P<day>[^/]+)/(?P<scene_nr>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    base_name='sentinel',
)
router.register(
    r'(?P<landsat>landsat)/(?P<collection>[^/]+)/(?P<sensor>[^/]+)/(?P<row>[^/]+)/(?P<column>[^/]+)/(?P<scene>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    base_name='landsat',
)
router.register(
    r'(?P<landsat>landsat)/(?P<sensor>[^/]+)/(?P<row>[^/]+)/(?P<column>[^/]+)/(?P<scene>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    base_name='landsat',
)
router.register(
    r'(?P<naip>naip)/(?P<state>[^/]+)/(?P<year>[^/]+)/(?P<resolution>[^/]+)/(?P<img_src>rgb|rgbir)/(?P<quadrangle>[^/]+)/(?P<scene>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    base_name='naip',
)
router.register(
    r'(?P<naip>naip)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    base_name='naip_auto',
)
router.register(
    r'(?P<naip>naip)/(?P<year>2011|2012|2013|2014|2015|2016)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    base_name='naip_auto_year',
)
router.register(
    r'(?P<composite>composite)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    base_name='composite_layer',
)

router.register(r'aggregationlayer', AggregationLayerViewSet)
router.register(r'aggregationarea', AggregationAreaViewSet)
router.register(r'valuecountresult', ValueCountResultViewSet)

router.register(r'composite', CompositeViewSet, base_name='composite')
router.register(r'compositetile', CompositeTileViewSet, base_name='compositetile')
router.register(r'compositebuild', CompositeBuildViewSet, base_name='compositebuild')
router.register(r'sentineltileaggregationlayer', SentinelTileAggregationLayerViewSet, base_name='sentineltileaggregationlayer')
router.register(r'sentineltile', SentinelTileViewSet, base_name='sentineltile')

router.register(r'formula', FormulaViewSet, base_name='formula')
router.register(r'wmtslayer', WMTSLayerViewSet, base_name='wmtslayer')

router.register(r'traininglayer', TrainingLayerViewSet, base_name='traininglayer')
router.register(r'trainingsample', TrainingSampleViewSet, base_name='trainingsample')
router.register(r'classifier', ClassifierViewSet, base_name='classifier')
router.register(r'predictedlayer', PredictedLayerViewSet, base_name='predictedlayer')

router.register(r'user', UserViewSet, base_name='user')
router.register(r'group', GroupViewSet, base_name='group')
router.register(r'readonlytoken', ReadOnlyTokenViewSet, base_name='readonlytoken')

apiurlpatterns = [
    url(r'^api/token-auth/', csrf_exempt(ObtainExpiringAuthToken.as_view())),
    url(r'^api/token-logout/', RemoveAuthToken.as_view()),
    url(r'^api/wmts/', WMTSAPIView.as_view(), name='wmts-service'),
    url(r'^api/', include(router.urls)),
]
