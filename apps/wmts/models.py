from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase

from django.contrib.gis.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from formulary.models import Formula
from sentinel.const import BAND_CHOICES
from sentinel.models import Composite, CompositeBand, SentinelTile, SentinelTileBand


class WMTSLayer(models.Model):
    title = models.CharField(max_length=200)
    formula = models.ForeignKey(Formula, null=True, blank=True, help_text='Assumes RGB mode if left blank.', on_delete=models.CASCADE)
    sentineltile = models.ForeignKey(SentinelTile, on_delete=models.CASCADE, null=True, blank=True)
    composite = models.ForeignKey(Composite, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        layer = self.sentineltile if self.sentineltile else self.composite
        layer_type = 'Scene' if self.sentineltile else 'Composite'
        formula = self.formula if self.formula else 'RGB'
        return '{} - {} for {} "{}"'.format(self.title, formula, layer_type, layer)

    class Meta:
        permissions = (
            ('view_wmtslayer', 'View WMTS layer'),
        )

    @property
    def formula_ids(self):
        ids = []
        if self.sentineltile:
            qs = self.sentineltile.sentineltileband_set.all()
            layer_attr = 'layer_id'
            doesnotexist = SentinelTileBand.DoesNotExist
        else:
            qs = self.composite.compositeband_set.all()
            layer_attr = 'rasterlayer_id'
            doesnotexist = CompositeBand.DoesNotExist

        for tpl in BAND_CHOICES:
            key = tpl[0]
            form_key = ''.join(key.split('.')[0].split('0'))
            if form_key in self.formula.formula:
                try:
                    ids.append('{}={}'.format(form_key, getattr(qs.get(band=key), layer_attr)))
                except doesnotexist:
                    continue
        return ','.join(ids)

    @property
    def rgb_ids(self):
        if self.sentineltile:
            return (
                self.sentineltile.sentineltileband_set.get(band='B04.jp2').layer_id,
                self.sentineltile.sentineltileband_set.get(band='B03.jp2').layer_id,
                self.sentineltile.sentineltileband_set.get(band='B02.jp2').layer_id,
            )
        else:
            return (
                self.composite.compositeband_set.get(band='B04.jp2').rasterlayer_id,
                self.composite.compositeband_set.get(band='B03.jp2').rasterlayer_id,
                self.composite.compositeband_set.get(band='B02.jp2').rasterlayer_id,
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
