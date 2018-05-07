from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase

from django.contrib.gis.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from sentinel.const import BAND_CHOICES
from sentinel.models import SentinelTile, SentinelTileBand


class Formula(models.Model):
    """
    Sentinel-2 ready formulas.
    """
    COLOR_CHOICES = (
        ('BrBG', 'BrBG'),
        ('PRGn', 'PRGn'),
        ('PiYG', 'PiYG'),
        ('PuOr', 'PuOr'),
        ('RdBu', 'RdBu'),
        ('RdGy', 'RdGy'),
        ('RdYlBu', 'RdYlBu'),
        ('RdYlGn', 'RdYlGn'),
        ('Spectral', 'Spectral'),
        ('Blues', 'Blues'),
        ('Greens', 'Greens'),
        ('Greys', 'Greys'),
        ('Oranges', 'Oranges'),
        ('Purples', 'Purples'),
        ('Reds', 'Reds'),
        ('BuGn', 'BuGn'),
        ('BuPu', 'BuPu'),
        ('GnBu', 'GnBu'),
        ('OrRd', 'OrRd'),
        ('PuBuGn', 'PuBuGn'),
        ('PuBu', 'PuBu'),
        ('PuRd', 'PuRd'),
        ('RdPu', 'RdPu'),
        ('YlGnBu', 'YlGnBu'),
        ('YlGn', 'YlGn'),
        ('YlOrBr', 'YlOrBr'),
        ('YlOrRd', 'YlOrRd'),
    )

    name = models.CharField(max_length=200)
    acronym = models.CharField(max_length=50, default='')
    description = models.TextField(default='')
    formula = models.TextField()
    min_val = models.FloatField()
    max_val = models.FloatField()
    breaks = models.IntegerField(default=5)
    color_palette = models.CharField(max_length=50, choices=COLOR_CHOICES)

    def __str__(self):
        return self.name


class FormulaUserObjectPermission(UserObjectPermissionBase):
    content_object = models.ForeignKey(Formula, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.user, self.permission, self.content_object)


class FormulaGroupObjectPermission(GroupObjectPermissionBase):
    content_object = models.ForeignKey(Formula, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} | {1} | {2}'.format(self.group, self.permission, self.content_object)


class PublicFormula(models.Model):

    formula = models.OneToOneField(Formula, on_delete=models.CASCADE)
    public = models.BooleanField(default=False)

    def __str__(self):
        return '{0} | {1}'.format(self.formula, 'public' if self.public else 'private')


@receiver(post_save, sender=Formula, weak=False, dispatch_uid="create_formula_public_object")
def create_formula_public_object(sender, instance, created, **kwargs):
    """
    Automatically create the public formula object.
    """
    if created:
        PublicFormula.objects.create(formula=instance)


class WMTSLayer(models.Model):
    title = models.CharField(max_length=200)
    formula = models.ForeignKey(Formula, null=True, help_text='Assumes RGB mode if left blank.', on_delete=models.CASCADE)
    sentineltile = models.ForeignKey(SentinelTile, on_delete=models.CASCADE)

    def __str__(self):
        return '{0} - {1}'.format(self.formula, self.sentineltile)

    @property
    def layer_ids(self):
        ids = []
        for tpl in BAND_CHOICES:
            key = tpl[0]
            form_key = ''.join(key.split('.')[0].split('0'))
            if form_key in self.formula.formula:
                try:
                    ids.append('='.join(form_key, str(self.sentineltile.sentineltileband_set.get(band=key).only('pk').pk)))
                except SentinelTileBand.DoesNotExist:
                    continue
        return ','.join(ids)


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
