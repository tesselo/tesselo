from django.contrib.gis import admin
from sentinel_1.models import Sentinel1Tile

admin.site.register(Sentinel1Tile, admin.OSMGeoAdmin)
