from django.contrib.gis import admin
from jobs import ecs
from sentinel_1.models import Sentinel1Tile, Sentinel1TileBand


class Sentinel1TileAdmin(admin.OSMGeoAdmin):
    actions = ['snap_terrain_correction', ]
    search_fields = ('prefix', )
    list_filter = ('status', )

    def snap_terrain_correction(self, request, queryset):
        """
        Parses the sentinel-s2-l1c bucket on S3.
        """
        for s1tile in queryset:
            ecs.snap_terrain_correction(s1tile.id)

        self.message_user(request, 'Triggered terrain correction for scenes {}'.format([s1tile.id for s1tile in queryset]))


class Sentinel1TileBandAdmin(admin.ModelAdmin):
    readonly_fields = ('tile', 'band', 'layer', )
    raw_id_fields = ('tile', 'layer', )


admin.site.register(Sentinel1Tile, Sentinel1TileAdmin)
admin.site.register(Sentinel1TileBand, Sentinel1TileBandAdmin)
