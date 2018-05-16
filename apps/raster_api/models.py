from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase
from raster.models import Legend, LegendSemantics, RasterLayer
from raster_aggregation.models import AggregationLayer

from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from sentinel.models import Composite, CompositeBuild, SentinelTileAggregationLayer


class RasterLayerUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(RasterLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class RasterLayerGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(RasterLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicRasterLayer(models.Model):

    rasterlayer = models.OneToOneField(RasterLayer, on_delete=models.CASCADE)
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

    legend = models.OneToOneField(Legend, on_delete=models.CASCADE)
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
    content_object = models.ForeignKey(LegendSemantics, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class LegendSemanticsGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(LegendSemantics, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicLegendSemantics(models.Model):

    legendsemantics = models.OneToOneField(LegendSemantics, on_delete=models.CASCADE)
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


class AggregationLayerUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(AggregationLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class AggregationLayerGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(AggregationLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicAggregationLayer(models.Model):

    aggregationlayer = models.OneToOneField(AggregationLayer, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.aggregationlayer, 'public' if self.public else 'private')


@receiver(post_save, sender=AggregationLayer, weak=False, dispatch_uid="create_aggregationlayer_public_object")
def create_aggregationlayer_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public aggregation layer object.
    """
    if created:
        PublicAggregationLayer.objects.create(aggregationlayer=instance)


class CompositeUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(Composite, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class CompositeGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(Composite, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicComposite(models.Model):

    composite = models.OneToOneField(Composite, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.composite, 'public' if self.public else 'private')


@receiver(post_save, sender=Composite, weak=False, dispatch_uid="create_composite_public_object")
def create_composite_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public composite object.
    """
    if created:
        PublicComposite.objects.create(composite=instance)


class SentinelTileAggregationLayerUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(SentinelTileAggregationLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class SentinelTileAggregationLayerGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(SentinelTileAggregationLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicSentinelTileAggregationLayer(models.Model):

    sentineltileaggregationlayer = models.OneToOneField(SentinelTileAggregationLayer, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.sentineltileaggregationlayer, 'public' if self.public else 'private')


@receiver(post_save, sender=SentinelTileAggregationLayer, weak=False, dispatch_uid="create_sentineltileaggregationlayer_public_object")
def create_sentineltileaggregationlayer_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public sentineltileaggregationlayer object.
    """
    if created:
        PublicSentinelTileAggregationLayer.objects.create(sentineltileaggregationlayer=instance)


class CompositeBuildUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(CompositeBuild, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class CompositeBuildGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(CompositeBuild, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicCompositeBuild(models.Model):

    compositebuild = models.OneToOneField(CompositeBuild, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.compositebuild, 'public' if self.public else 'private')


@receiver(post_save, sender=CompositeBuild, weak=False, dispatch_uid="create_compositebuild_public_object")
def create_compositebuild_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public compositebuild object.
    """
    if created:
        PublicCompositeBuild.objects.create(compositebuild=instance)
