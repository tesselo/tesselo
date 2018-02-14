from __future__ import unicode_literals

from django.contrib.gis import admin
from sentinel.models import (
    BucketParseLog, Composite, CompositeBand, CompositeBuildLog, MGRSTile, SentinelTile, SentinelTileAggregationLayer,
    SentinelTileBand, ZoneOfInterest
)
from sentinel.tasks import drive_composite_builders, drive_sentinel_bucket_parser, upgrade_sentineltile_to_l2a


class PatchedOSMGeoAdmin(admin.GeoModelAdmin):
    openlayers_url = 'https://openlayers.org/api/2.13.1/OpenLayers.js'


class BucketParseLogModelAdmin(admin.ModelAdmin):
    actions = ['parse_bucket', ]
    readonly_fields = ('utm_zone', 'start', 'end', 'log', )

    def parse_bucket(self, request, queryset):
        """
        Parses the sentinel-s2-l1c bucket on S3.
        """
        run_ecs_command('python36 manage.py sentinel drive_sentinel_bucket_parser')
        self.message_user(request, 'Started parsing the "sentinel-s2-l1c" bucket on S3.')


class SentinelTileBandAdmin(admin.ModelAdmin):
    readonly_fields = ('tile', 'band', 'layer', )
    raw_id_fields = ('tile', 'layer', )


class SentinelTileCompositeInline(admin.TabularInline):
    model = SentinelTile.composite_set.through
    extra = 1


class SentinelTileAdmin(PatchedOSMGeoAdmin):
    actions = ('upgrade_to_l2a', )
    readonly_fields = (
        'prefix', 'datastrip', 'product_name', 'angle_altitude',
        'angle_azimuth', 'data_coverage_percentage',
        'cloudy_pixel_percentage', 'collected', 'mgrstile', 'level',
    )
    raw_id_fields = ('mgrstile', )
    modifiable = False
    list_filter = ('mgrstile__utm_zone', 'mgrstile__latitude_band', )
    search_fields = ('prefix', )
    inlines = (SentinelTileCompositeInline, )

    def upgrade_to_l2a(self, request, queryset):
        for tile in queryset:
            run_ecs_command('python36 manage.py sentinel process_l2a {}'.format(tile.id))
        self.message_user(request, 'Triggered update for all tile bands to L2A.')


class MGRSTileAdmin(PatchedOSMGeoAdmin):
    listfilter = ('utm_zone', 'latitude_band')
    readonly_fields = (
        'utm_zone', 'latitude_band', 'grid_square',
    )
    modifiable = False
    list_filter = ('utm_zone', 'latitude_band', )


class CompositeAdmin(admin.ModelAdmin):
    list_filter = ('active', )
    model = Composite
    readonly_fields = ('compositebands', 'sentineltiles', )
    actions = ['build_composite', ]

    def build_composite(self, request, queryset):
        """
        Admin action to build selected compositebands.
        """
        drive_composite_builders([lyr.id for lyr in queryset])
        self.message_user(request, 'Started building compositebands.')


class ZoneOfInterestAdmin(PatchedOSMGeoAdmin):
    list_filter = ('active', )


class SentinelTileAggregationLayerAdmin(admin.ModelAdmin):
    raw_id_fields = ('sentineltile', )


admin.site.register(BucketParseLog, BucketParseLogModelAdmin)
admin.site.register(SentinelTileBand, SentinelTileBandAdmin)
admin.site.register(SentinelTile, SentinelTileAdmin)
admin.site.register(MGRSTile, MGRSTileAdmin)
admin.site.register(ZoneOfInterest, ZoneOfInterestAdmin)
admin.site.register(CompositeBand)
admin.site.register(CompositeBuildLog)
admin.site.register(Composite, CompositeAdmin)
admin.site.register(SentinelTileAggregationLayer, SentinelTileAggregationLayerAdmin)
