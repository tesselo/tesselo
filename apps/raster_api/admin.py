from django.contrib import admin
from raster_api.models import PublicRasterLayer, RasterLayerGroupObjectPermission, RasterLayerUserObjectPermission

admin.site.register(PublicRasterLayer)
admin.site.register(RasterLayerUserObjectPermission)
admin.site.register(RasterLayerGroupObjectPermission)
