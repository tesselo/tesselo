from django.contrib.gis.db import models


class NAIPQuadrangle(models.Model):
    NW = 'nw'
    NE = 'ne'
    SW = 'sw'
    SE = 'se'
    CORNER_CHOICES = (
        (NW, 'North West'),
        (NE, 'North East'),
        (SW, 'South West'),
        (SE, 'South East'),
    )

    RGBIR = 'rgbir'
    RGB = 'rgb'
    SOURCE_CHOICES = (
        (RGBIR, '4-Band Uncompressed'),
        (RGB, '3-Band JPEG Compressed and tiled internally'),
    )

    prefix = models.CharField(max_length=500, unique=True)

    lat = models.IntegerField(db_index=True)
    lon = models.IntegerField(db_index=True)
    subquad = models.IntegerField(db_index=True)
    corner = models.CharField(max_length=2, choices=CORNER_CHOICES, db_index=True)
    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, db_index=True)

    state = models.CharField(max_length=50)
    date = models.DateField(db_index=True)
    resolution = models.CharField(max_length=50)

    def __str__(self):
        return self.prefix
