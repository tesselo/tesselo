from django.contrib.gis import admin
from sentinel_1.models import Sentinel1Tile, Sentinel1TileBand

admin.site.register(Sentinel1Tile, admin.OSMGeoAdmin)
admin.site.register(Sentinel1TileBand)
