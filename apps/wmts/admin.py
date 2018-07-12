from django.contrib import admin
from wmts.models import WMTSLayer


class WMTSLayerAdmin(admin.ModelAdmin):
    raw_id_fields = ('sentineltile', 'composite', )


admin.site.register(WMTSLayer, WMTSLayerAdmin)
