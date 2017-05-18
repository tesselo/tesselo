from __future__ import unicode_literals

from raster.models import Legend, LegendSemantics, RasterLayer

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
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


@receiver(post_save, sender=RasterLayer, weak=False, dispatch_uid="create_rasterlayer_public_object")
def create_rasterlayer_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public rasterlayer object.
    """
    if created:
        PublicRasterLayer.objects.create(rasterlayer=instance)


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


@receiver(post_save, sender=Legend, weak=False, dispatch_uid="create_legend_public_object")
def create_legend_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public legend object.
    """
    if created:
        PublicLegend.objects.create(legend=instance)


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


@receiver(post_save, sender=LegendSemantics, weak=False, dispatch_uid="create_legendsemantics_public_object")
def create_legendsemantics_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public legend semantics object.
    """
    if created:
        PublicLegendSemantics.objects.create(legendsemantics=instance)
