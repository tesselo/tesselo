from guardian.models import GroupObjectPermissionBase, UserObjectPermissionBase

from django.contrib.gis.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from formulary import colorbrewer


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

    @property
    def colormap(self):
        # Select color palette.
        DEFAULT_COLOR = 'RdYlGn'
        palette = self.color_palette if self.color_palette else DEFAULT_COLOR
        # Create discrete or continuous colormap.
        if self.breaks > 0:
            # Compute nr of breaks (limit at 9 due to colorberwer).
            breaks = max(self.breaks, 9)
            # Get color palette by name and number of breaks.
            brew = getattr(colorbrewer, palette)[breaks]
            # Compute value increment for discrete binning.
            delta = (self.max_val - self.min_val) / breaks
            # Construct colormap.
            colormap = {}
            for i in range(breaks):
                # Compute formula expression.
                expression = '{}<x<{}'.format(
                    self.min_val + i * delta,
                    self.min_val + (i + 1) * delta,
                )
                # Set color for this range.
                # colormap[expression] = brew[i]
                colormap[expression] = colorbrewer.convert(brew[i]) + [0]
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
