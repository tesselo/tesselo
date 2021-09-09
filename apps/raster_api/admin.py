from django.contrib import admin, messages
from django.http import HttpResponseRedirect
from guardian.admin import GuardedModelAdmin
from raster.admin import LegendAdmin, RasterLayerModelAdmin
from raster.models import Legend, RasterLayer
from raster_aggregation.admin import ComputeActivityAggregatesModelAdmin
from raster_aggregation.models import AggregationLayer
from rest_framework.authtoken.admin import TokenAdmin

from raster_api.models import (
    PublicAggregationLayer, PublicLegend, PublicRasterLayer, ReadOnlyToken, TesseloUserAccount
)


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


class CustomTokenAdmin(TokenAdmin):
    actions = ['refresh_token']

    def refresh_token(self, request, queryset):
        """
        Refresh a read only token by deleting it and creating a new one.
        """
        if len(queryset) > 1:
            messages.error(request, "Please select only one token to refresh")
            return HttpResponseRedirect(request.get_full_path())

        old_token = queryset[0]
        user = old_token.user
        old_token.delete()
        new_token = ReadOnlyToken.objects.create(user=user)
        messages.success(request, f"New token created, please copy it: {new_token.key}")
        return HttpResponseRedirect(request.get_full_path())


admin.site.unregister(AggregationLayer)
admin.site.register(AggregationLayer, GuardedAggregationLayerModelAdmin)
admin.site.register(PublicAggregationLayer)
admin.site.register(TesseloUserAccount)
admin.site.register(ReadOnlyToken, CustomTokenAdmin)
