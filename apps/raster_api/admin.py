from django.contrib import admin
from raster_api.models import (
    LegendGroupObjectPermission, LegendSemanticsGroupObjectPermission, LegendSemanticsUserObjectPermission,
    LegendUserObjectPermission, PublicLegend, PublicLegendSemantics, PublicRasterLayer,
    RasterLayerGroupObjectPermission, RasterLayerUserObjectPermission
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
