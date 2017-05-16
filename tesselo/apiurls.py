from rest_framework import routers

from raster_aggregation.views import (
    AggregationAreaGeoViewSet, AggregationAreaValueViewSet, AggregationAreaViewSet, AggregationLayerViewSet
)
from raster_api.views import (
    AlgebraAPIView, ExportAPIView, LegendEntryViewSet, LegendSemanticsViewSet, LegendViewSet, RasterLayerViewSet
)

router = routers.DefaultRouter(trailing_slash=False)

router.register(r'rasterlayer', RasterLayerViewSet)
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

router.register(r'aggregationareageo', AggregationAreaGeoViewSet, base_name='aggregationareageo')
router.register(r'aggregationarea', AggregationAreaViewSet, base_name='aggregationarea')
router.register(r'aggregationareavalue', AggregationAreaValueViewSet, base_name='aggregationareavalue')
router.register(r'aggregationlayer', AggregationLayerViewSet, base_name='aggregationlayer')
