from django.contrib import admin
from raster_api.models import RasterLayerUserObjectPermission, RasterLayerGroupObjectPermission, PublicRasterLayer

admin.site.register(PublicRasterLayer)
admin.site.register(RasterLayerUserObjectPermission)
admin.site.register(RasterLayerGroupObjectPermission)
