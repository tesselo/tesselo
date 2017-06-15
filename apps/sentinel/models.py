from __future__ import unicode_literals

import datetime

from raster.models import RasterLayer, RasterLayerParseStatus
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE, WEB_MERCATOR_WORLDSIZE
from raster.tiles.utils import tile_index_range

from django.contrib.gis.db import models
from django.contrib.gis.gdal import SpatialReference
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from sentinel import const


class MGRSTile(models.Model):
    """
    Military grid reference system tiles.
    """
    utm_zone = models.CharField(max_length=2)
    latitude_band = models.CharField(max_length=1)
    grid_square = models.CharField(max_length=2)
    geom = models.PolygonField(null=True)

    def __str__(self):
        return self.code

    @property
    def code(self):
        return '{}{}{}'.format(self.utm_zone, self.latitude_band, self.grid_square)

    class Meta:
        unique_together = (("utm_zone", "latitude_band", "grid_square"),)


class SentinelTile(models.Model):
    """
    Sentinel-2 tiles at Level 1C.
    """
    prefix = models.TextField(unique=True)
    datastrip = models.TextField()
    product_name = models.TextField()
    mgrstile = models.ForeignKey(MGRSTile)
    tile_data_geom = models.MultiPolygonField(null=True)
    collected = models.DateTimeField()
    cloudy_pixel_percentage = models.FloatField()
    data_coverage_percentage = models.FloatField()
    angle_azimuth = models.FloatField(default=0)
    angle_altitude = models.FloatField(default=0)

    def __str__(self):
        return '{0} {1}'.format(self.mgrstile.code, self.collected)

    @property
    def url(self):
        return const.BUCKET_URL + self.prefix

    @property
    def complete(self):
        """
        Return true if all sentinel tiles were parsed successfuly.
        """
        qs = self.sentineltileband_set.all()
        all_finished = (band.layer.parselog.status == RasterLayerParseStatus.FINISHED for band in qs)
        return sum(all_finished) == len(const.BAND_CHOICES)


class SentinelTileBand(models.Model):
    """
    Sentinel tile band (aka Granule) ingested as raster layer.
    """
    tile = models.ForeignKey(SentinelTile)
    band = models.CharField(max_length=7, choices=const.BAND_CHOICES)
    layer = models.OneToOneField(RasterLayer)

    class Meta:
        unique_together = (("tile", "band"),)

    def __str__(self):
        return 'Tile {0} - Layer {1} - {2}'.format(self.tile.mgrstile, self.layer_id, self.get_band_display())

    @property
    def resolution(self):
        return const.BAND_RESOLUTIONS[self.band]


class BucketParseLog(models.Model):
    """
    Track parse attempts and progress.
    """
    utm_zone = models.CharField(max_length=3)
    start = models.DateTimeField()
    end = models.DateTimeField(null=True)
    log = models.TextField(default='')

    def __str__(self):
        return 'Utm Zone {0}, {1}'.format(self.utm_zone, self.start)

    def write(self, data):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        self.save()


class ZoneOfInterest(models.Model):
    """
    Store zones for which sentinel data shall be ingested.
    """
    name = models.CharField(max_length=500)
    geom = models.PolygonField()
    active = models.BooleanField(default=True, help_text='If unchecked, this area will not be included in the parsing.')

    def __str__(self):
        return self.name

    def index_range(self, zoom):
        geom = self.geom.transform(WEB_MERCATOR_SRID, clone=True)
        return tile_index_range(geom.extent, zoom, tolerance=1e-3)


class WorldLayer(models.Model):
    """
    Register RasterLayers as big kahunas.
    """
    band = models.CharField(max_length=7, choices=const.BAND_CHOICES)
    rasterlayer = models.ForeignKey(RasterLayer)

    def __str__(self):
        return '{} - {}'.format(self.band, self.rasterlayer.name)


class WorldLayerGroup(models.Model):
    """
    A set of rasterlayers containing composits of sentinel scenes.
    """
    # Name of the group.
    name = models.CharField(max_length=500)
    # Zones of interest relevant for this group.
    zonesofinterest = models.ManyToManyField(ZoneOfInterest, blank=True, help_text='What zones should this layer be built for?')
    all_zones = models.BooleanField(default=False, help_text='If checked, this layer will be built for all zones of interest.')
    # One raster layer for each band.
    worldlayers = models.ManyToManyField(WorldLayer, editable=False)
    # Defining parameters of the layer group.
    min_date = models.DateField()
    max_date = models.DateField()
    max_cloudy_pixel_percentage = models.FloatField(default=100)
    # Parse related data.
    active = models.BooleanField(default=True, help_text='If unchecked, this area will not be included in the parsing.')

    def __str__(self):
        return self.name

    @property
    def kahunas(self):
        return {lyr.band: lyr.rasterlayer_id for lyr in self.worldlayers.all()}


@receiver(post_save, sender=WorldLayerGroup)
def create_worldlayer_group_layers(sender, instance, created, **kwargs):
    """
    Creates a world layer for each Sentinel band.
    """
    if not created:
        return

    for band, description in const.BAND_CHOICES:
        raster = RasterLayer.objects.create(name='{0} - {1}'.format(instance.name, band))
        # Update metadata item.
        nr_of_pixels = WEB_MERCATOR_TILESIZE * 2 ** const.ZOOM_LEVEL_10M

        raster.metadata.uperleftx = -WEB_MERCATOR_WORLDSIZE / 2
        raster.metadata.uperlefty = WEB_MERCATOR_WORLDSIZE / 4
        raster.metadata.width = nr_of_pixels
        raster.metadata.height = nr_of_pixels / 2
        raster.metadata.scalex = WEB_MERCATOR_WORLDSIZE / nr_of_pixels
        raster.metadata.scaley = -WEB_MERCATOR_WORLDSIZE / nr_of_pixels
        raster.metadata.skewx = 0
        raster.metadata.skewy = 0
        raster.metadata.numbands = 1
        raster.metadata.srs_wkt = SpatialReference(WEB_MERCATOR_SRID).wkt
        raster.metadata.srid = WEB_MERCATOR_SRID
        raster.metadata.max_zoom = const.ZOOM_LEVEL_10M

        raster.metadata.save()
        # Update parse status to parsed.
        raster.parsestatus.status = RasterLayerParseStatus.FINISHED
        raster.parsestatus.save()
        # Create worldlayer for this band.
        world = WorldLayer.objects.create(band=band, rasterlayer=raster)
        instance.worldlayers.add(world)


class WorldParseProcess(models.Model):
    """
    Track parsing processes to prevent duplication.
    """
    worldlayergroup = models.ForeignKey(WorldLayerGroup)

    tilex = models.IntegerField()
    tiley = models.IntegerField()
    tilez = models.IntegerField()

    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.end:
            if not self.start:
                duration = 'Completed'
            else:
                duration = 'Completed in {0}'.format(self.end - self.start)
        elif self.start:
            duration = 'Running since {0}'.format(timezone.now() - self.start)
        else:
            duration = 'Not started yet'

        return '{0} - {1}/{2}/{3} - {4}'.format(
            self.worldlayergroup.name,
            self.tilez,
            self.tilex,
            self.tiley,
            duration,
        )
