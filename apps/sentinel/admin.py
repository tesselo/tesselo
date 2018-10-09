from guardian.admin import GuardedModelAdmin

from django.contrib.gis import admin
from sentinel import ecs
from sentinel.models import (
    BucketParseLog, Composite, CompositeBand, CompositeBuild, CompositeTile, MGRSTile, SentinelTile,
    SentinelTileAggregationLayer, SentinelTileBand, SentinelTileSceneClass
)


class BucketParseLogModelAdmin(admin.ModelAdmin):
    actions = ['parse_bucket', ]
    readonly_fields = ('utm_zone', 'start', 'end', 'log', )
    list_filter = ('status', )

    def parse_bucket(self, request, queryset):
        """
        Parses the sentinel-s2-l1c bucket on S3.
        """
        ecs.drive_sentinel_bucket_parser()
        self.message_user(request, 'Started parsing the "sentinel-s2-l1c" bucket on S3.')


class SentinelTileBandAdmin(admin.ModelAdmin):
    readonly_fields = ('tile', 'band', 'layer', )
    raw_id_fields = ('tile', 'layer', )


class SentinelTileCompositeInline(admin.TabularInline):
    model = SentinelTile.composite_set.through
    extra = 1


class SentinelTileAdmin(admin.OSMGeoAdmin):
    actions = ('upgrade_to_l2a', )
    readonly_fields = (
        'prefix', 'datastrip', 'product_name', 'angle_altitude',
        'angle_azimuth', 'data_coverage_percentage',
        'cloudy_pixel_percentage', 'collected', 'mgrstile', 'level',
    )
    raw_id_fields = ('mgrstile', )
    modifiable = False
    list_filter = ('mgrstile__utm_zone', 'mgrstile__latitude_band', 'status', )
    search_fields = ('prefix', )
    inlines = (SentinelTileCompositeInline, )

    def upgrade_to_l2a(self, request, queryset):
        for tile in queryset:
            ecs.process_l2a(tile.id)
            tile.status = SentinelTile.PENDING
            tile.save()

        self.message_user(request, 'Triggered L2A updates for scenes {}'.format([tile.id for tile in queryset]))


class MGRSTileAdmin(admin.OSMGeoAdmin):
    listfilter = ('utm_zone', 'latitude_band')
    readonly_fields = (
        'utm_zone', 'latitude_band', 'grid_square',
    )
    modifiable = False
    list_filter = ('utm_zone', 'latitude_band', )


class CompositeAdmin(GuardedModelAdmin):
    list_filter = ('active', )
    model = Composite
    readonly_fields = ('sentineltiles', )


class SentinelTileAggregationLayerAdmin(admin.ModelAdmin):
    raw_id_fields = ('sentineltile', )


class SentinelTileSceneClassAdmin(admin.ModelAdmin):
    raw_id_fields = ('tile', 'layer', )


class CompositeBuildAdmin(admin.ModelAdmin):
    model = CompositeBuild
    readonly_fields = ('sentineltiles', 'compositetiles', )
    actions = ('run_composite_build', )
    list_filter = ('status', )

    def run_composite_build(self, request, queryset):
        for build in queryset:
            build.status = CompositeBuild.PENDING
            build.save()
            ecs.composite_build_callback(build.id, initiate=True, rebuild=True)

        self.message_user(request, 'Triggered Composite Builds {}'.format([build.id for build in queryset]))


class CompositeTileAdmin(admin.ModelAdmin):
    list_filter = ('status', )
    actions = ('build_composite_tile', )

    def build_composite_tile(self, request, queryset):
        for ctile in queryset:
            ctile.status = CompositeTile.PENDING
            ctile.save()
            ecs.process_compositetile(ctile.id)

        self.message_user(request, 'Triggered Composite Tile Builds {}'.format([ctile.id for ctile in queryset]))


class CompositeBandAdmin(admin.ModelAdmin):
    raw_id_fields = ('rasterlayer', 'composite', )


admin.site.register(BucketParseLog, BucketParseLogModelAdmin)
admin.site.register(SentinelTileBand, SentinelTileBandAdmin)
admin.site.register(SentinelTile, SentinelTileAdmin)
admin.site.register(MGRSTile, MGRSTileAdmin)
admin.site.register(CompositeBand, CompositeBandAdmin)
admin.site.register(CompositeTile, CompositeTileAdmin)
admin.site.register(CompositeBuild, CompositeBuildAdmin)
admin.site.register(Composite, CompositeAdmin)
admin.site.register(SentinelTileAggregationLayer, SentinelTileAggregationLayerAdmin)
admin.site.register(SentinelTileSceneClass, SentinelTileSceneClassAdmin)
