import calendar
import datetime

from raster.models import RasterLayer
from raster.tiles.const import WEB_MERCATOR_SRID
from raster.tiles.utils import tile_index_range
from raster_aggregation.models import AggregationLayer

from django.contrib.auth.models import User
from django.contrib.gis.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.dateparse import parse_date
from sentinel import const
from sentinel.utils import populate_raster_metadata


def get_duration(obj):
    if obj.end:
        if not obj.start:
            return ''
        else:
            return '{0}'.format(obj.end - obj.start)
    elif obj.start:
        return '{0}'.format(timezone.now() - obj.start)
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
    prefix = models.TextField(unique=True, db_index=True)
    datastrip = models.TextField()
    product_name = models.TextField()
    mgrstile = models.ForeignKey(MGRSTile, on_delete=models.CASCADE)
    tile_geom = models.PolygonField(null=True)
    tile_data_geom = models.MultiPolygonField(null=True)
    collected = models.DateTimeField(db_index=True)
    cloudy_pixel_percentage = models.FloatField(db_index=True)
    data_coverage_percentage = models.FloatField()
    angle_azimuth = models.FloatField(default=0)
    angle_altitude = models.FloatField(default=0)
    level = models.CharField(max_length=10, choices=const.PROCESS_LEVELS, default=const.LEVEL_L1C)
    status = models.CharField(max_length=20, choices=ST_STATUS_CHOICES, default=UNPROCESSED, db_index=True)
    log = models.TextField(default='', blank=True)

    def __str__(self):
        return '{} | {} | {}'.format(self.mgrstile.code, self.collected.date(), self.status)

    def write(self, data, status=None, level=None):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        if status:
            self.status = status
        if level:
            self.level = level
        self.save()

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

    @property
    def srid(self):
        """
        The raster srid is in the 32600 range if in the northern hemisphere,
        otherwise 32700. The last two digits is the UTM zone number.
        """
        srid = 32600 if self.tile_geom.extent[3] > 0 else 32700
        return srid + int(self.mgrstile.utm_zone)


class SentinelTileBand(models.Model):
    """
    Sentinel tile band (aka Granule) ingested as raster layer.
    """
    tile = models.ForeignKey(SentinelTile, on_delete=models.CASCADE)
    band = models.CharField(max_length=7, choices=const.BAND_CHOICES)
    layer = models.OneToOneField(RasterLayer, on_delete=models.CASCADE)

    class Meta:
        unique_together = (("tile", "band"),)

    def __str__(self):
        return 'Tile {0} - Layer {1} - {2}'.format(self.tile.mgrstile, self.layer_id, self.get_band_display())

    @property
    def resolution(self):
        return const.BAND_RESOLUTIONS[self.band]


class SentinelTileSceneClass(models.Model):
    """
    Sen2Cor Scene classification for a sentinel tile.
    """
    tile = models.OneToOneField(SentinelTile, on_delete=models.CASCADE)
    layer = models.OneToOneField(RasterLayer, on_delete=models.CASCADE)

    def __str__(self):
        return 'Tile {0} - SceneClass - Layer {1}'.format(self.tile.mgrstile, self.layer_id)


class SentinelTileAggregationLayer(models.Model):
    sentineltile = models.ForeignKey(SentinelTile, on_delete=models.CASCADE)
    aggregationlayer = models.ForeignKey(AggregationLayer, on_delete=models.CASCADE)
    active = models.BooleanField(default=True)

    class Meta:
        unique_together = (('sentineltile', 'aggregationlayer'),)

    def __str__(self):
        return '{} | {} | {}'.format(self.sentineltile, self.aggregationlayer, 'active ' if self.active else 'not active')


class BucketParseLog(models.Model):
    """
    Track parse attempts and progress.
    """
    PENDING = 'Pending'
    PROCESSING = 'Processing'
    FINISHED = 'Finished'
    FAILED = 'Failed'
    BUCKET_PARSE_STATUS_CHOICES = (
        (PENDING, PENDING),
        (PROCESSING, PROCESSING),
        (FINISHED, FINISHED),
        (FAILED, FAILED),
    )

    utm_zone = models.CharField(max_length=3)
    scheduled = models.DateTimeField()
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)
    log = models.TextField(default='', blank=True)
    status = models.CharField(max_length=20, choices=BUCKET_PARSE_STATUS_CHOICES)

    def __str__(self):
        dat = 'Utm Zone {0} {1}'.format(self.utm_zone, self.status)
        if self.status == self.FINISHED:
            if self.end:
                dat += ' (completed in {0})'.format(get_duration(self))
            else:
                dat += ' (no end time)'
        return dat

    def write(self, data, status=None):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        if status:
            self.status = status
        self.save()


class CompositeBand(models.Model):
    """
    Register RasterLayers as rasterlayer_lookup.
    """
    band = models.CharField(max_length=7, choices=const.BAND_CHOICES)
    rasterlayer = models.ForeignKey(RasterLayer, on_delete=models.CASCADE)
    composite = models.ForeignKey('Composite', on_delete=models.CASCADE, null=True)

    class Meta:
        unique_together = (("composite", "band"), )

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
    # Defining parameters of the layer group.
    min_date = models.DateField(null=True, blank=True)
    max_date = models.DateField(null=True, blank=True)
    max_cloudy_pixel_percentage = models.FloatField(default=100)
    sentineltiles = models.ManyToManyField(SentinelTile, blank=True, help_text='Limit the composite to a specific set of sentinel tiles.')
    # Parse related data.
    active = models.BooleanField(default=True, help_text='If unchecked, this area will not be included in the parsing.')
    official = models.BooleanField(default=False)
    interval = models.CharField(max_length=200, choices=INTERVAL_CHOICES, default=CUSTOM, editable=False)

    def __str__(self):
        return '{} ({} to {})'.format(self.name, self.min_date, self.max_date)

    @property
    def rasterlayer_lookup(self):
        return {lyr.band: lyr.rasterlayer_id for lyr in self.compositeband_set.all()}

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

        if min_date.day == 1 and max_date.day == calendar.monthrange(max_date.year, max_date.month)[1] and min_date.month == max_date.month:
            self.interval = self.MONTHLY
        elif calendar.weekday(min_date.year, min_date.month, min_date.day) == calendar.MONDAY and calendar.weekday(max_date.year, max_date.month, max_date.day) == calendar.SUNDAY:
            self.interval = self.WEEKLY
        else:
            self.interval = self.CUSTOM

        super(Composite, self).save(*args, **kwargs)

    def get_sentineltiles(self):
        if self.sentineltiles.count() > 0:
            # Get specific sentinel tiles if specified.
            qs = self.sentineltiles.all()
        else:
            # Preload tiles that are populated on the bands based on the composite
            # layer group settings.
            qs = SentinelTile.objects.filter(
                collected__gte=self.min_date,
                collected__lte=self.max_date,
                cloudy_pixel_percentage__lte=self.max_cloudy_pixel_percentage,
            )
        # Return data ordered by decending date.
        return qs.order_by('-collected')


@receiver(post_save, sender=Composite)
def create_compositeband_layers(sender, instance, created, **kwargs):
    """
    Creates a composite for each Sentinel band.
    """
    if not created:
        return

    for band, description in const.BAND_CHOICES:
        raster = RasterLayer.objects.create(name='{0} - {1}'.format(instance.name, band))
        populate_raster_metadata(raster)
        # Create compositeband for this band.
        CompositeBand.objects.create(band=band, rasterlayer=raster, composite=instance)


class CompositeTile(models.Model):
    """
    Track parsing processes to prevent duplication.
    """
    UNPROCESSED = 'Unprocessed'
    PENDING = 'Pending'
    PROCESSING = 'Processing'
    FINISHED = 'Finished'
    FAILED = 'Failed'
    CT_STATUS_CHOICES = (
        (UNPROCESSED, UNPROCESSED),
        (PENDING, PENDING),
        (PROCESSING, PROCESSING),
        (FINISHED, FINISHED),
        (FAILED, FAILED),
    )

    composite = models.ForeignKey(Composite, on_delete=models.CASCADE)

    tilex = models.IntegerField()
    tiley = models.IntegerField()
    tilez = models.IntegerField()

    scheduled = models.DateTimeField(null=True, blank=True)
    start = models.DateTimeField(null=True, blank=True)
    end = models.DateTimeField(null=True, blank=True)

    created = models.DateTimeField(auto_now_add=True)
    log = models.TextField(default='', blank=True)
    status = models.CharField(max_length=20, choices=CT_STATUS_CHOICES, default=UNPROCESSED)
    cloud_version = models.IntegerField(null=True, blank=True, help_text='Leave empty to use latest version.')
    cloud_classifier = models.ForeignKey('classify.Classifier', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        unique_together = (("composite", "tilez", "tilex", "tiley"), )

    def __str__(self):
        return '{0} - {1}/{2}/{3} - {4} - Ran for {5}'.format(
            self.composite.name,
            self.tilez,
            self.tilex,
            self.tiley,
            self.status,
            get_duration(self),
        )

    def write(self, data, status=None):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        if status:
            self.status = status
        self.save()

    def get_version_string(self):
        if self.cloud_classifier_id:
            return 'Classifier {}'.format(self.cloud_classifier_id)
        else:
            return 'Version {}'.format(self.cloud_version)


class CompositeBuild(models.Model):
    """
    Build tracker for composites.
    """
    UNPROCESSED = 'Unprocessed'
    PENDING = 'Pending'
    INGESTING_SCENES = 'Ingesting Scenes'
    BUILDING_TILES = 'Building Composite Tiles'
    FINISHED = 'Finished'
    FAILED = 'Failed'
    CB_STATUS_CHOICES = (
        (UNPROCESSED, UNPROCESSED),
        (PENDING, PENDING),
        (INGESTING_SCENES, INGESTING_SCENES),
        (BUILDING_TILES, BUILDING_TILES),
        (FINISHED, FINISHED),
        (FAILED, FAILED),
    )
    composite = models.ForeignKey(Composite, on_delete=models.CASCADE)
    aggregationlayer = models.ForeignKey(AggregationLayer, on_delete=models.CASCADE)
    log = models.TextField(default='', blank=True)
    status = models.CharField(max_length=50, choices=CB_STATUS_CHOICES, default=UNPROCESSED, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    sentineltiles = models.ManyToManyField(SentinelTile)
    compositetiles = models.ManyToManyField(CompositeTile)
    cloud_version = models.IntegerField(null=True, blank=True, help_text='Leave empty to use latest version.')
    cloud_classifier = models.ForeignKey('classify.Classifier', null=True, blank=True, on_delete=models.SET_NULL, help_text='Use a classifier based cloud removal. The classifier is assumed to return a cloud probability or rank (the higher the output the more likely its a cloud). If specified, the cloud_version flag is ignored.')

    def __str__(self):
        return '{} - {} - {}'.format(self.composite, self.aggregationlayer, self.status)

    def write(self, data, status=None):
        now = '[{0}] '.format(datetime.datetime.now().strftime('%Y-%m-%d %T'))
        self.log += now + str(data) + '\n'
        if status:
            self.status = status
        self.save()

    def set_sentineltiles(self):
        # Clear current set of sentineltiles.
        self.sentineltiles.clear()
        # Get SentinelTiles that need processing.
        sentineltiles = self.composite.get_sentineltiles()
        # Remove the first and last UTM Zone. The geometries there need fixing
        # bacause they span the whole world, instead of wrap around the timezone
        # horizon.
        sentineltiles = sentineltiles.exclude(
            prefix__startswith='tiles/1/',
        ).exclude(
            prefix__startswith='tiles/60/',
        )
        # Build list of unique IDS for SentinelTiles that intersect with the
        # aggregation layer.
        for aggarea in self.aggregationlayer.aggregationarea_set.all():
            for stile in sentineltiles.filter(tile_data_geom__bboverlaps=aggarea.geom):
                self.sentineltiles.add(stile)

    def set_compositetiles(self):
        # Create set to hold tile indexes.
        indexranges = set()
        # Loop through all aggregationareas.
        for aggarea in self.aggregationlayer.aggregationarea_set.all():
            # Get index range from aggregationarea.
            geom = aggarea.geom.transform(WEB_MERCATOR_SRID, clone=True)
            indexrange = tile_index_range(geom.extent, const.ZOOM_LEVEL_WORLDLAYER, tolerance=1e-3)
            # Add additional tiles to set.
            for tilex in range(indexrange[0], indexrange[2] + 1):
                for tiley in range(indexrange[1], indexrange[3] + 1):
                    indexranges.add((tilex, tiley, const.ZOOM_LEVEL_WORLDLAYER))
        # Clear current set of compositetiles.
        self.compositetiles.clear()
        # Assign the required composite tiles.
        for tilex, tiley, tilez in indexranges:
            ctile, created = CompositeTile.objects.get_or_create(
                composite=self.composite,
                tilex=tilex,
                tiley=tiley,
                tilez=tilez,
            )
            self.compositetiles.add(ctile)
