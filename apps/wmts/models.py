from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase

from classify.models import PredictedLayer
from django.contrib.gis.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from formulary.models import Formula
from sentinel.models import Composite, CompositeBand, SentinelTile, SentinelTileBand


class WMTSLayer(models.Model):
    title = models.CharField(max_length=200)
    formula = models.ForeignKey(Formula, null=True, blank=True, help_text='Assumes RGB mode if left blank.', on_delete=models.CASCADE)
    sentineltile = models.ForeignKey(SentinelTile, on_delete=models.CASCADE, null=True, blank=True)
    composite = models.ForeignKey(Composite, on_delete=models.CASCADE, null=True, blank=True)
    predictedlayer = models.ForeignKey(PredictedLayer, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        if self.sentineltile:
            layer = self.sentineltile
            layer_type = 'Scene'
            formula = self.formula if self.formula else 'RGB'
        elif self.predictedlayer:
            layer = self.predictedlayer
            layer_type = 'Predicted layer'
            formula = 'Result'
        else:
            layer = self.composite
            layer_type = 'Composite'
            formula = self.formula if self.formula else 'RGB'
        return '{} - {} for {} "{}"'.format(self.title, formula, layer_type, layer)

    @property
    def url(self):
        if self.formula:
            return self.formula_url
        elif self.predictedlayer:
            return self.predictedlayer_url
        else:
            return self.rgb_url

    @property
    def rgb_url(self):
        if self.sentineltile:
            try:
                red = self.sentineltile.sentineltileband_set.get(band='B04.jp2').layer_id
                green = self.sentineltile.sentineltileband_set.get(band='B03.jp2').layer_id
                blue = self.sentineltile.sentineltileband_set.get(band='B02.jp2').layer_id
            except SentinelTileBand.DoesNotExist:
                return
        else:
            try:
                red = self.composite.compositeband_set.get(band='B04.jp2').rasterlayer_id
                green = self.composite.compositeband_set.get(band='B03.jp2').rasterlayer_id
                blue = self.composite.compositeband_set.get(band='B02.jp2').rasterlayer_id
            except CompositeBand.DoesNotExist:
                return

        # Generate RGB url.
        return "algebra/{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png?layers=r={red},g={green},b={blue}&amp;scale=0,1e4&amp;alpha&amp;enhance_brightness=3.0&amp;enhance_sharpness=1.2&amp;enhance_color=1.9&amp;enhance_contrast=1.5".format(
            red=red,
            green=green,
            blue=blue,
        )

    @property
    def formula_url(self):
        # Get layer type and ID from layer spec.
        if self.sentineltile:
            layer_id = self.sentineltile.id
            layer_type = 'scene'
        else:
            layer_id = self.composite.id
            layer_type = 'composite'

        # Generate formula tile url.
        return "formula/{formula_id}/{layer_type}/{layer_id}/{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png".format(
            formula_id=self.formula.id,
            layer_type=layer_type,
            layer_id=layer_id,
        )

    @property
    def predictedlayer_url(self):
        return "tile/{predictedlayer}/{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png".format(
            predictedlayer=self.predictedlayer.rasterlayer_id,
        )


class WMTSLayerUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(WMTSLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class WMTSLayerGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(WMTSLayer, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicWMTSLayer(models.Model):
    wmtslayer = models.OneToOneField(WMTSLayer, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.wmtslayer, 'public' if self.public else 'private')


@receiver(post_save, sender=WMTSLayer, weak=False, dispatch_uid="create_wmtslayer_public_object")
def create_wmtslayer_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public wmts layer object.
    """
    if created:
        PublicWMTSLayer.objects.create(wmtslayer=instance)
