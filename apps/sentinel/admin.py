from __future__ import unicode_literals

from django.contrib.gis import admin
from sentinel.models import (
    BucketParseLog, MGRSTile, SentinelTile, SentinelTileBand, WorldLayer, WorldLayerGroup, WorldParseProcess,
    ZoneOfInterest
)
from sentinel.tasks import drive_sentinel_bucket_parser, drive_world_layers


class PatchedOSMGeoAdmin(admin.OSMGeoAdmin):
    openlayers_url = 'https://cdnjs.cloudflare.com/ajax/libs/openlayers/2.13.1/OpenLayers.js'


class BucketParseLogModelAdmin(admin.ModelAdmin):
    actions = ['parse_bucket', ]
    readonly_fields = ('utm_zone', 'start', 'end', 'log', )

    def parse_bucket(self, request, queryset):
        """
        Parses the sentinel-s2-l1c bucket on S3.
        """
        drive_sentinel_bucket_parser.delay()
        self.message_user(request, 'Started parsing the "sentinel-s2-l1c" bucket on S3.')


class SentinelTileBandAdmin(admin.ModelAdmin):
    readonly_fields = ('tile', 'band', 'layer', )
    raw_id_fields = ('tile', 'layer', )


class SentinelTileAdmin(PatchedOSMGeoAdmin):
    readonly_fields = (
        'prefix', 'datastrip', 'product_name', 'angle_altitude',
        'angle_azimuth', 'data_coverage_percentage',
        'cloudy_pixel_percentage', 'collected', 'mgrstile'
    )
    raw_id_fields = ('mgrstile', )
    modifiable = False


class MGRSTileAdmin(PatchedOSMGeoAdmin):
    listfilter = ('utm_zone', 'latitude_band')
    readonly_fields = (
        'utm_zone', 'latitude_band', 'grid_square',
    )
    modifiable = False


class WorldLayerGroupAdmin(admin.ModelAdmin):
    list_filter = ('active', )
    model = WorldLayerGroup
    readonly_fields = ('worldlayers', )
    actions = ['build_worldlayers', ]

    def build_worldlayers(self, request, queryset):
        """
        Admin action to build selected worldlayers.
        """
        drive_world_layers.delay([lyr.id for lyr in queryset])
        self.message_user(request, 'Started building worldlayers.')


class ZoneOfInterestAdmin(PatchedOSMGeoAdmin):
    list_filter = ('active', )


admin.site.register(BucketParseLog, BucketParseLogModelAdmin)
admin.site.register(SentinelTileBand, SentinelTileBandAdmin)
admin.site.register(SentinelTile, SentinelTileAdmin)
admin.site.register(MGRSTile, MGRSTileAdmin)
admin.site.register(ZoneOfInterest, ZoneOfInterestAdmin)
admin.site.register(WorldLayer)
admin.site.register(WorldParseProcess)
admin.site.register(WorldLayerGroup, WorldLayerGroupAdmin)
