import datetime

from raster.models import RasterLayer

from django.contrib.gis.db import models
from django.contrib.postgres.fields import HStoreField
from sentinel_1 import const


class Sentinel1Tile(models.Model):
    """
    Sentinel-1 tiles.
    """
    UNPROCESSED = 'Unprocessed'
    PENDING = 'Pending'
    PROCESSING = 'Processing'
    FINISHED = 'Finished'
    FAILED = 'Failed'
    BROKEN = 'Broken'
    ST_STATUS_CHOICES = (
        (UNPROCESSED, UNPROCESSED),
        (PENDING, PENDING),
        (PROCESSING, PROCESSING),
        (FINISHED, FINISHED),
        (FAILED, FAILED),
        (BROKEN, BROKEN),
    )
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
    footprint = models.MultiPolygonField(null=True)
    filename_map = HStoreField()
    status = models.CharField(max_length=20, choices=ST_STATUS_CHOICES, default=UNPROCESSED, db_index=True)
    log = models.TextField(default='', blank=True)

    def __str__(self):
        return self.prefix

    def write(self, data, status=None):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        if status:
            self.status = status
        self.save()


class Sentinel1TileBand(models.Model):
    tile = models.ForeignKey(Sentinel1Tile, on_delete=models.CASCADE)
    band = models.CharField(max_length=7, choices=const.BAND_CHOICES)
    layer = models.OneToOneField(RasterLayer, on_delete=models.CASCADE)

    class Meta:
        unique_together = (("tile", "band"),)

    def __str__(self):
        return 'Tile {0} - Layer {1} - {2}'.format(self.tile.prefix, self.layer_id, self.get_band_display())
