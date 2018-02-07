from __future__ import unicode_literals

import calendar
import datetime

from raster.models import RasterLayer, RasterLayerParseStatus
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE, WEB_MERCATOR_WORLDSIZE
from raster.tiles.utils import tile_index_range
from raster_aggregation.models import AggregationLayer

from django.contrib.gis.db import models
from django.contrib.gis.gdal import SpatialReference
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.dateparse import parse_date
from sentinel import const


def get_duration(obj):
        if obj.end:
            if not obj.start:
                return 'Completed'
            else:
                return 'Completed in {0}'.format(obj.end - obj.start)
        elif obj.start:
            return 'Running since {0}'.format(timezone.now() - obj.start)
        else:
            return 'Not started yet'


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
    Sentinel-2 tiles.
    """
    prefix = models.TextField(unique=True)
    datastrip = models.TextField()
    product_name = models.TextField()
    mgrstile = models.ForeignKey(MGRSTile)
    tile_geom = models.PolygonField(null=True)
    tile_data_geom = models.MultiPolygonField(null=True)
    collected = models.DateTimeField()
    cloudy_pixel_percentage = models.FloatField()
    data_coverage_percentage = models.FloatField()
    angle_azimuth = models.FloatField(default=0)
    angle_altitude = models.FloatField(default=0)
    level = models.CharField(max_length=10, choices=const.PROCESS_LEVELS, default=const.LEVEL_L1C)

    def __str__(self):
        return '{0} {1}'.format(self.mgrstile.code, self.collected)

    @property
    def complete(self):
        """
        Return true if all sentinel tiles were parsed successfuly.
        """
        if not self.has_rasters:
            return False
        qs = self.sentineltileband_set.all()
        all_finished = (band.layer.parsestatus.status == RasterLayerParseStatus.FINISHED for band in qs)
        return sum(all_finished) == len(const.BAND_CHOICES)

    def get_source_url(self, band):
        if self.level == const.LEVEL_L1C:
            return const.BUCKET_URL + self.prefix + band
        else:
            return '{bucket}{prefix}R{resolution}m/{band}'.format(
                bucket=const.L2A_BUCKET,
                prefix=self.prefix,
                resolution=const.BAND_RESOLUTIONS[band],
                band=band,
            )

    def upgrade_to_l2a(self):
        # Return if the product is already at Level 2.
        if self.level == const.LEVEL_L2A:
            return

        # Abort if image is before L2A avaliablitiy cutoff.
        if self.collected.date() < const.L2A_AVAILABILITY_DATE:
            return

        # Update level.
        self.level = const.LEVEL_L2A
        self.save()

        # Update raster layers with L2A bucket addresses, which triggers
        # re-parsing.
        for band in self.sentineltileband_set.all():
            band.layer.source_url = self.get_source_url(band.band)
            band.layer.save()

    @property
    def rasterlayer_lookup(self):
        return {band.band: band.layer_id for band in self.sentineltileband_set.all()}


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


class SentinelTileAggregationLayer(models.Model):
    sentineltile = models.ForeignKey(SentinelTile)
    aggregationlayer = models.ForeignKey(AggregationLayer)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = (('sentineltile', 'aggregationlayer'),)

    def __str__(self):
        return '{} | {} | {}'.format(self.sentineltile, self.aggregationlayer, 'active ' if self.active else 'not active')


class BucketParseLog(models.Model):
    """
    Track parse attempts and progress.
    """
    utm_zone = models.CharField(max_length=3)
    start = models.DateTimeField()
    end = models.DateTimeField(null=True)
    log = models.TextField(default='')

    def __str__(self):
        return 'Utm Zone {0}, {1}'.format(self.utm_zone, get_duration(self))

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


class CompositeBand(models.Model):
    """
    Register RasterLayers as rasterlayer_lookup.
    """
    band = models.CharField(max_length=7, choices=const.BAND_CHOICES)
    rasterlayer = models.ForeignKey(RasterLayer)

    def __str__(self):
        return '{} - {}'.format(self.band, self.rasterlayer.name)


class Composite(models.Model):
    """
    A set of rasterlayers containing composits of sentinel scenes.
    """
    WEEKLY = 'Weekly'
    MONTHLY = 'Monthly'
    CUSTOM = 'Custom'
    INTERVAL_CHOICES = (
        (WEEKLY, WEEKLY),
        (MONTHLY, MONTHLY),
        (CUSTOM, CUSTOM),
    )
    # Name of the group.
    name = models.CharField(max_length=500)
    # Zones of interest relevant for this group.
    zonesofinterest = models.ManyToManyField(ZoneOfInterest, blank=True, help_text='What zones should this layer be built for?')
    aggregationlayers = models.ManyToManyField(AggregationLayer, blank=True, help_text='What aggregation layers should this layer be built for?')
    all_zones = models.BooleanField(default=False, help_text='If checked, this layer will be built for all zones of interest.')
    # One raster layer for each band.
    compositebands = models.ManyToManyField(CompositeBand, editable=False)
    # Defining parameters of the layer group.
    min_date = models.DateField(null=True, blank=True)
    max_date = models.DateField(null=True, blank=True)
    max_cloudy_pixel_percentage = models.FloatField(default=100)
    sentineltiles = models.ManyToManyField(SentinelTile, blank=True, help_text='Limit the composite to a specific set of sentinel tiles.')
    # Parse related data.
    active = models.BooleanField(default=True, help_text='If unchecked, this area will not be included in the parsing.')
    official = models.BooleanField(default=False, editable=False)
    interval = models.CharField(max_length=200, choices=INTERVAL_CHOICES, default=CUSTOM, editable=False)

    def __str__(self):
        return self.name

    @property
    def rasterlayer_lookup(self):
        return {lyr.band: lyr.rasterlayer_id for lyr in self.compositebands.all()}

    def save(self, *args, **kwargs):
        """
        Compute interval field based on dates.
        """
        min_date = self.min_date
        if isinstance(min_date, str):
            min_date = parse_date(min_date)

        max_date = self.max_date
        if isinstance(max_date, str):
            max_date = parse_date(max_date)

        if min_date.day == 1 and max_date.day == calendar.monthrange(max_date.year, max_date.month)[1]:
            self.interval = self.MONTHLY
        elif calendar.weekday(min_date.year, min_date.month, min_date.day) == calendar.MONDAY and calendar.weekday(max_date.year, max_date.month, max_date.day) == calendar.SUNDAY:
            self.interval = self.WEEKLY
        else:
            self.interval = self.CUSTOM

        super(Composite, self).save(*args, **kwargs)


@receiver(post_save, sender=Composite)
def create_compositeband_layers(sender, instance, created, **kwargs):
    """
    Creates a composite for each Sentinel band.
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
        # Create compositeband for this band.
        world = CompositeBand.objects.create(band=band, rasterlayer=raster)
        instance.compositebands.add(world)


class CompositeBuildLog(models.Model):
    """
    Track parsing processes to prevent duplication.
    """
    composite = models.ForeignKey(Composite)

    tilex = models.IntegerField()
    tiley = models.IntegerField()
    tilez = models.IntegerField()

    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    log = models.TextField(default='')

    def __str__(self):
        return '{0} - {1}/{2}/{3} - {4}'.format(
            self.composite.name,
            self.tilez,
            self.tilex,
            self.tiley,
            get_duration(self),
        )

    def write(self, data):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        self.save()
