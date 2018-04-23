from django.contrib.gis.db import models
from django.contrib.postgres.fields import HStoreField


class Sentinel1Tile(models.Model):
    """
    Sentinel-1 tiles.
    """
    product_name = models.TextField()
    prefix = models.TextField(unique=True)
    mission_id = models.TextField()
    product_type = models.TextField()
    mode = models.TextField()
    polarization = models.TextField()
    start_time = models.DateTimeField()
    stop_time = models.DateTimeField()
    absolute_orbit_number = models.IntegerField()
    mission_datatake_id = models.IntegerField()
    product_unique_identifier = models.TextField()
    sci_hub_id = models.TextField()
    footprint = models.PolygonField(null=True)
    filename_map = HStoreField()

    def __str__(self):
        return self.prefix
