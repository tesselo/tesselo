from django.contrib import admin
from raster_api.models import (
    AggregationLayerGroupObjectPermission, AggregationLayerUserObjectPermission, LegendGroupObjectPermission,
    LegendSemanticsGroupObjectPermission, LegendSemanticsUserObjectPermission, LegendUserObjectPermission,
    PublicAggregationLayer, PublicLegend, PublicLegendSemantics, PublicRasterLayer, PublicValueCountResult,
    RasterLayerGroupObjectPermission, RasterLayerUserObjectPermission, ValueCountResultGroupObjectPermission,
    ValueCountResultUserObjectPermission
)

admin.site.register(PublicRasterLayer)
admin.site.register(RasterLayerUserObjectPermission)
admin.site.register(RasterLayerGroupObjectPermission)
admin.site.register(PublicLegend)
admin.site.register(LegendUserObjectPermission)
admin.site.register(LegendGroupObjectPermission)
admin.site.register(PublicLegendSemantics)
admin.site.register(LegendSemanticsUserObjectPermission)
admin.site.register(LegendSemanticsGroupObjectPermission)
admin.site.register(AggregationLayerUserObjectPermission)
admin.site.register(AggregationLayerGroupObjectPermission)
admin.site.register(PublicAggregationLayer)
admin.site.register(ValueCountResultUserObjectPermission)
admin.site.register(ValueCountResultGroupObjectPermission)
admin.site.register(PublicValueCountResult)
