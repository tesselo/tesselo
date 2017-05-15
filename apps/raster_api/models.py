from __future__ import unicode_literals

from raster.models import Legend, LegendSemantics, RasterLayer

from django.db import models
from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase


class RasterLayerUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(RasterLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class RasterLayerGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(RasterLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicRasterLayer(models.Model):

    rasterlayer = models.OneToOneField(RasterLayer)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.rasterlayer, 'public' if self.public else 'private')


class LegendUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(Legend, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class LegendGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(Legend, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicLegend(models.Model):

    legend = models.OneToOneField(Legend)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.legend, 'public' if self.public else 'private')


class LegendSemanticsUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(Legend, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class LegendSemanticsGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(Legend, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicLegendSemantics(models.Model):

    legendsemantics = models.OneToOneField(LegendSemantics)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.legendsemantics, 'public' if self.public else 'private')
