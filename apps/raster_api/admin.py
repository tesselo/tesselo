from guardian.admin import GuardedModelAdmin
from raster.admin import LegendAdmin, RasterLayerModelAdmin
from raster.models import Legend, RasterLayer
from raster_aggregation.admin import ComputeActivityAggregatesModelAdmin
from raster_aggregation.models import AggregationLayer

from django.contrib import admin
from raster_api.models import PublicAggregationLayer, PublicLegend, PublicRasterLayer


class GuardedRasterLayerModelAdmin(RasterLayerModelAdmin, GuardedModelAdmin):
    pass


admin.site.unregister(RasterLayer)
admin.site.register(RasterLayer, GuardedRasterLayerModelAdmin)
admin.site.register(PublicRasterLayer)


class GuardedLegendModelAdmin(LegendAdmin, GuardedModelAdmin):
    pass


admin.site.unregister(Legend)
admin.site.register(Legend, GuardedLegendModelAdmin)
admin.site.register(PublicLegend)


class GuardedAggregationLayerModelAdmin(ComputeActivityAggregatesModelAdmin, GuardedModelAdmin):
    pass


admin.site.unregister(AggregationLayer)
admin.site.register(AggregationLayer, GuardedAggregationLayerModelAdmin)
admin.site.register(PublicAggregationLayer)
