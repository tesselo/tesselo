from django.contrib.gis import admin
from formulary.models import Formula, WMTSLayer


class WMTSLayerAdmin(admin.ModelAdmin):
    raw_id_fields = ('sentineltile', )


admin.site.register(Formula)
admin.site.register(WMTSLayer, WMTSLayerAdmin)
