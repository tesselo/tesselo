from django.contrib.gis import admin
from naip.models import NAIPQuadrangle


class NAIPQuadrangleModelAdmin(admin.ModelAdmin):
    search_fields = ('prefix', )
    list_filter = ('state', 'source', 'lat', 'lon', 'subquad', )


admin.site.register(NAIPQuadrangle, NAIPQuadrangleModelAdmin)
