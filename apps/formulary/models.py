from django.contrib.gis.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase
from raster.models import Legend

from classify.models import PredictedLayer
from formulary import colorbrewer
from sentinel.models import Composite


class Formula(models.Model):
    """
    Sentinel-1 and Sentinel-2 ready formulas.
    """
    S1 = 'S1'
    S2 = 'S2'
    PLATFORM_CHOICES = (
        (S1, 'Sentinel-1'),
        (S2, 'Sentinel-2'),
    )
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

    DEFAULT_COLOR = 'RdYlGn'

    name = models.CharField(max_length=200)
    acronym = models.CharField(max_length=50, default='')
    description = models.TextField(default='')
    # Algebra settings.
    formula = models.TextField(null=True, blank=True)
    min_val = models.FloatField(null=True, blank=True)
    max_val = models.FloatField(null=True, blank=True)
    breaks = models.IntegerField(default=5, null=True, blank=True)
    color_palette = models.CharField(max_length=50, choices=COLOR_CHOICES, null=True, blank=True)
    discrete = models.BooleanField(default=False)
    legend = models.ForeignKey(Legend, null=True, blank=True, on_delete=models.SET_NULL)
    composite = models.ForeignKey(Composite, null=True, blank=True, on_delete=models.SET_NULL)
    # RGB settings.
    rgb = models.BooleanField(default=False, help_text='Choose RGB vs Formula mode. If true the layer is rendered as RGB, otherwise as raster algebra.')
    rgb_platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default=S2, help_text='Choose Platform for RGB interpretation.')
    rgb_enhance_brightness = models.FloatField(default=3.0, null=True, blank=True)
    rgb_enhance_sharpness = models.FloatField(default=1.2, null=True, blank=True)
    rgb_enhance_color = models.FloatField(default=1.9, null=True, blank=True)
    rgb_enhance_contrast = models.FloatField(default=1.5, null=True, blank=True)
    rgb_scale_min = models.FloatField(default=0, null=True, blank=True)
    rgb_scale_max = models.FloatField(default=1e4, null=True, blank=True)
    rgb_alpha = models.BooleanField(default=False, null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def colormap(self):
        # Select color palette.
        palette = self.color_palette if self.color_palette else self.DEFAULT_COLOR
        # Create discrete or continuous colormap.
        if self.legend:
            return self.legend.colormap
        elif self.breaks is not None and self.breaks > 0:
            # Compute nr of breaks (limit between 2 and 9 due to colorberwer).
            breaks = max(min(self.breaks, 9), 2)
            # Get color palette by name and number of breaks.
            brew = getattr(colorbrewer, palette)[breaks]
            # Compute value increment for discrete binning.
            delta = (self.max_val - self.min_val) / breaks
            # Construct colormap.
            colormap = {}
            for i in range(breaks):
                # Compute formula expression.
                expression = '({}<=x)&(x<{})'.format(
                    self.min_val + i * delta,
                    self.min_val + (i + 1) * delta,
                )
                # Set color for this range.
                colormap[expression] = colorbrewer.convert(brew[i]) + [255]
            return colormap
        else:
            # Get color palette by name.
            brew = getattr(colorbrewer, palette)[9]
            return {
                "continuous": True,
                "range": [self.min_val, self.max_val],
                "from": colorbrewer.convert(brew[0]),
                "over": colorbrewer.convert(brew[4]),
                "to": colorbrewer.convert(brew[8]),
            }


class PredictedLayerFormula(models.Model):
    formula = models.ForeignKey(Formula, on_delete=models.CASCADE)
    predictedlayer = models.ForeignKey(PredictedLayer, on_delete=models.CASCADE)
    key = models.CharField(max_length=20, help_text='Key used for this layer in formula expression. Should only contain alphanumeric characters and no whitespace.')

    def __str__(self):
        return '{} | {}'.format(self.formula, self.predictedlayer)

    def save(self, *args, **kwargs):
        # Remove any non-alphanumeric characters from the key.
        self.key = ''.join(dat for dat in self.key if dat.isalnum())
        super(PredictedLayerFormula, self).save(*args, **kwargs)


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
