from guardian.models import UserObjectPermissionBase
from guardian.models import GroupObjectPermissionBase

from raster.models import RasterLayer
from django.db import models


class RasterLayerUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(RasterLayer, on_delete=models.CASCADE)


class RasterLayerGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(RasterLayer, on_delete=models.CASCADE)
