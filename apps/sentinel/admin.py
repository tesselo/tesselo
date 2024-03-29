from django.contrib.gis import admin
from guardian.admin import GuardedModelAdmin

from jobs import ecs
from sentinel.models import (
    BucketParseLog, Composite, CompositeBand, CompositeBuild, CompositeBuildSchedule, CompositeTile, MGRSTile,
    SentinelTile, SentinelTileAggregationLayer, SentinelTileBand, SentinelTileSceneClass
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
    model = Composite
    raw_id_fields = ('sentineltiles', 'sentinel1tiles', )
    list_display = ('name', 'min_date', 'max_date')
    search_fields = ('name', )
    list_filter = ('active', 'min_date', 'max_date', 'interval', )


class SentinelTileAggregationLayerAdmin(admin.ModelAdmin):
    raw_id_fields = ('sentineltile', )


class SentinelTileSceneClassAdmin(admin.ModelAdmin):
    raw_id_fields = ('tile', 'layer', )


class CompositeBuildAdmin(admin.ModelAdmin):
    model = CompositeBuild
    readonly_fields = ('sentineltiles', 'compositetiles', 'sentinel1tiles', )
    actions = ('run_composite_build', 'run_preflight')
    list_filter = ('status', 'include_sentinel_1', 'include_sentinel_2')
    search_fields = ('composite__name', 'aggregationlayer__name')
    raw_id_fields = ('composite', 'aggregationlayer', )

    def run_composite_build(self, request, queryset):
        for build in queryset:
            build.status = CompositeBuild.PENDING
            build.save()
            ecs.composite_build_callback(build.id, initiate=True, rebuild=True)

        self.message_user(request, 'Triggered Composite Builds {}'.format([build.id for build in queryset]))

    def run_preflight(self, request, queryset):
        for build in queryset:
            build.preflight()
        self.message_user(request, 'Computed preflight effort for Composite Builds {}'.format([build.id for build in queryset]))


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


class CompositeBuildScheduleAdmin(admin.ModelAdmin):
    raw_id_fields = ('compositebuilds', )


admin.site.register(BucketParseLog, BucketParseLogModelAdmin)
admin.site.register(SentinelTileBand, SentinelTileBandAdmin)
admin.site.register(SentinelTile, SentinelTileAdmin)
admin.site.register(MGRSTile, MGRSTileAdmin)
admin.site.register(CompositeBand, CompositeBandAdmin)
admin.site.register(CompositeTile, CompositeTileAdmin)
admin.site.register(CompositeBuild, CompositeBuildAdmin)
admin.site.register(CompositeBuildSchedule, CompositeBuildScheduleAdmin)
admin.site.register(Composite, CompositeAdmin)
admin.site.register(SentinelTileAggregationLayer, SentinelTileAggregationLayerAdmin)
admin.site.register(SentinelTileSceneClass, SentinelTileSceneClassAdmin)
