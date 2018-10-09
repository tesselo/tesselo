from guardian.admin import GuardedModelAdmin

from django.contrib import admin
from wmts.models import WMTSLayer


class WMTSLayerAdmin(GuardedModelAdmin):
    raw_id_fields = ('sentineltile', 'composite', )


admin.site.register(WMTSLayer, WMTSLayerAdmin)
