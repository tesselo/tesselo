from raster.models import Legend, RasterLayer

from django.db import models
from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase


class RasterLayerUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(RasterLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1}'.format(self.permission, self.content_object)


class RasterLayerGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(RasterLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1}'.format(self.permission, self.content_object)


class LegendUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(Legend, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1}'.format(self.permission, self.content_object)


class LegendGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(Legend, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1}'.format(self.permission, self.content_object)


class PublicRasterLayer(models.Model):

    rasterlayer = models.OneToOneField(RasterLayer)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.rasterlayer, 'public' if self.public else 'private')
