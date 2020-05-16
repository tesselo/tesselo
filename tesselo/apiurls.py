from rest_framework import routers

from classify.views import (
    ClassifierViewSet, PredictedLayerTileViewSet, PredictedLayerViewSet, TrainingLayerViewSet, TrainingSampleViewSet
)
from django.conf.urls import include, url
from django.views.decorators.csrf import csrf_exempt
from formulary.views import FormulaAlgebraAPIView, FormulaViewSet
from jobs.views import BatchJobViewSet
from raster_api.views import (
    AdminAlgebraAPIView, AggregationAreaViewSet, AggregationLayerVectorTilesViewSet, AggregationLayerViewSet,
    AlgebraAPIView, CompositeViewSet, ExportAPIView, LambdaView, LegendEntryViewSet, LegendSemanticsViewSet,
    LegendViewSet, ObtainExpiringAuthToken, RasterLayerViewSet, ReadOnlyTokenViewSet, RemoveAuthToken,
    SentinelTileAggregationLayerViewSet, ValueCountResultViewSet
)
from report.views import ReportAggregationViewSet, ReportScheduleViewSet
from sentinel.views import CompositeBuildViewSet, CompositeTileViewSet, SentinelTileViewSet
from userinterface.views import BookmarkFolderViewSet, BookmarkViewSet
from wmts.views import WMTSAPIView

router = routers.DefaultRouter(trailing_slash=False)

router.register(r'rasterlayer', RasterLayerViewSet)
router.register(r'legend', LegendViewSet)
router.register(r'legendsemantics', LegendSemanticsViewSet)
router.register(r'legendentry', LegendEntryViewSet)

router.register(
    r'tile/(?P<layer>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    AdminAlgebraAPIView,
    basename='tile'
)
router.register(
    r'algebra/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>jpg|png|tif)',
    AlgebraAPIView,
    basename='algebra'
)
router.register(
    r'^pixel/(?P<xcoord>-?\d+(?:\.\d+)?)/(?P<ycoord>-?\d+(?:\.\d+)?)$',
    AdminAlgebraAPIView,
    basename='algebra-pixel'
)
router.register(
    r'export',
    ExportAPIView,
    basename='export'
)
router.register(
    r'vtiles/(?P<aggregationlayer>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>json|pbf)',
    AggregationLayerVectorTilesViewSet,
    basename='vectortiles'
)
router.register(
    r'(?P<sentinel>sentinel)/(?P<utm_zone>[^/]+)/(?P<lat_band>[^/]+)/(?P<grid_id>[^/]+)/(?P<year>[^/]+)/(?P<month>[^/]+)/(?P<day>[^/]+)/(?P<scene_nr>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    basename='sentinel',
)
router.register(
    r'(?P<landsat>landsat)/(?P<collection>[^/]+)/(?P<sensor>[^/]+)/(?P<row>[^/]+)/(?P<column>[^/]+)/(?P<scene>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    basename='landsat',
)
router.register(
    r'(?P<landsat>landsat)/(?P<sensor>[^/]+)/(?P<row>[^/]+)/(?P<column>[^/]+)/(?P<scene>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    basename='landsat',
)
router.register(
    r'(?P<naip>naip)/(?P<state>[^/]+)/(?P<year>[^/]+)/(?P<resolution>[^/]+)/(?P<img_src>rgb|rgbir)/(?P<quadrangle>[^/]+)/(?P<scene>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    basename='naip',
)
router.register(
    r'(?P<naip>naip)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    basename='naip_auto',
)
router.register(
    r'(?P<naip>naip)/(?P<year>2011|2012|2013|2014|2015|2016)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    basename='naip_auto_year',
)
router.register(
    r'(?P<composite>composite)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    LambdaView,
    basename='composite_layer',
)

router.register(r'aggregationlayer', AggregationLayerViewSet)
router.register(r'aggregationarea', AggregationAreaViewSet)
router.register(r'valuecountresult', ValueCountResultViewSet)

router.register(r'composite', CompositeViewSet, basename='composite')
router.register(r'compositetile', CompositeTileViewSet, basename='compositetile')
router.register(r'compositebuild', CompositeBuildViewSet, basename='compositebuild')
router.register(r'sentineltileaggregationlayer', SentinelTileAggregationLayerViewSet, basename='sentineltileaggregationlayer')
router.register(r'sentineltile', SentinelTileViewSet, basename='sentineltile')

router.register(r'formula', FormulaViewSet, basename='formula')
router.register(
    r'formula/(?P<formula_id>[0-9]+)/(?P<layer_type>scene|composite)/(?P<layer_id>[0-9]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>jpg|png|tif)',
    FormulaAlgebraAPIView,
    basename='formula_algebra'
)

router.register(r'traininglayer', TrainingLayerViewSet, basename='traininglayer')
router.register(r'trainingsample', TrainingSampleViewSet, basename='trainingsample')
router.register(r'classifier', ClassifierViewSet, basename='classifier')
router.register(r'predictedlayer', PredictedLayerViewSet, basename='predictedlayer')
router.register(
    r'predictedlayer/(?P<predictedlayer_id>[^/]+)/(?P<z>[0-9]+)/(?P<x>[0-9]+)/(?P<y>[0-9]+).(?P<frmt>png|jpg|tif)',
    PredictedLayerTileViewSet,
    basename='predictedlayer_tile'
)

router.register(r'readonlytoken', ReadOnlyTokenViewSet, basename='readonlytoken')

router.register(r'bookmark', BookmarkViewSet, basename='bookmark')
router.register(r'bookmarkfolder', BookmarkFolderViewSet, basename='bookmarkfolder')

router.register(r'reportschedule', ReportScheduleViewSet, basename='reportschedule')
router.register(r'reportaggregation', ReportAggregationViewSet, basename='reportaggregation')

router.register(r'batchjob', BatchJobViewSet, basename='batchjob')

apiurlpatterns = [
    url(r'^token-auth/', csrf_exempt(ObtainExpiringAuthToken.as_view()), name='api-token-auth'),
    url(r'^token-logout/', RemoveAuthToken.as_view(), name='api-token-logout'),
    url(r'^wmts/', WMTSAPIView.as_view(), name='wmts-service'),
    url(r'^', include(router.urls)),
]
