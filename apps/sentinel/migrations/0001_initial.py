# Generated by Django 2.0.2 on 2018-09-25 14:18

from django.conf import settings
import django.contrib.gis.db.models.fields
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('raster_aggregation', '0020_auto_20180308_0435'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('raster', '0039_merge_20171116_1051'),
    ]

    operations = [
        migrations.CreateModel(
            name='BucketParseLog',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('utm_zone', models.CharField(max_length=3)),
                ('scheduled', models.DateTimeField()),
                ('start', models.DateTimeField(null=True)),
                ('end', models.DateTimeField(null=True)),
                ('log', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Processing', 'Processing'), ('Finished', 'Finished'), ('Failed', 'Failed')], max_length=20)),
            ],
        ),
        migrations.CreateModel(
            name='Composite',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=500)),
                ('min_date', models.DateField(blank=True, null=True)),
                ('max_date', models.DateField(blank=True, null=True)),
                ('max_cloudy_pixel_percentage', models.FloatField(default=100)),
                ('active', models.BooleanField(default=True, help_text='If unchecked, this area will not be included in the parsing.')),
                ('official', models.BooleanField(default=False)),
                ('interval', models.CharField(choices=[('Weekly', 'Weekly'), ('Monthly', 'Monthly'), ('Custom', 'Custom')], default='Custom', editable=False, max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='CompositeBand',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('band', models.CharField(choices=[('B01.jp2', 'Band 1 - Coastal aerosol, WL 0.443 mu, RES 60 m'), ('B02.jp2', 'Band 2 - Blue, WL 0.490 mu, RES 10 m'), ('B03.jp2', 'Band 3 - Green, WL 0.560 mu, RES 10 m'), ('B04.jp2', 'Band 4 - Red WL 0.665 mu, RES 10m'), ('B05.jp2', 'Band 5 - Vegetation Red Edge, WL 0.705, RES 20 m'), ('B06.jp2', 'Band 6 - Vegetation Red Edge, WL 0.740, RES 20 m'), ('B07.jp2', 'Band 7 - Vegetation Red Edge, WL 0.783, RES 20 m'), ('B08.jp2', 'Band 8 - NIR, WL 0.842, RES 10 m'), ('B8A.jp2', 'Band 8A - Vegetation Red Edge, WL 0.865, RES 20 m'), ('B09.jp2', 'Band 9 - Water vapour, WL 0.945, RES 60 m'), ('B10.jp2', 'Band 10 - SWIR - Cirrus, WL 1.375, RES 60 m'), ('B11.jp2', 'Band 11 - SWIR, WL 1.610, RES 20 m'), ('B12.jp2', 'Band 12 - SWIR, WL 2.190, RES 20 m')], max_length=7)),
                ('composite', models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, to='sentinel.Composite')),
                ('rasterlayer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='raster.RasterLayer')),
            ],
        ),
        migrations.CreateModel(
            name='CompositeBuild',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('log', models.TextField(blank=True, default='')),
                ('status', models.CharField(blank=True, choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Ingesting Scenes', 'Ingesting Scenes'), ('Building Composite Tiles', 'Building Composite Tiles'), ('Finished', 'Finished'), ('Failed', 'Failed')], default='Unprocessed', max_length=50)),
                ('cloud_version', models.IntegerField(blank=True, help_text='Leave empty to use latest version.', null=True)),
                ('aggregationlayer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='raster_aggregation.AggregationLayer')),
                ('composite', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sentinel.Composite')),
            ],
        ),
        migrations.CreateModel(
            name='CompositeTile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tilex', models.IntegerField()),
                ('tiley', models.IntegerField()),
                ('tilez', models.IntegerField()),
                ('scheduled', models.DateTimeField(blank=True, null=True)),
                ('start', models.DateTimeField(blank=True, null=True)),
                ('end', models.DateTimeField(blank=True, null=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('log', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Processing', 'Processing'), ('Finished', 'Finished'), ('Failed', 'Failed')], default='Unprocessed', max_length=20)),
                ('cloud_version', models.IntegerField(blank=True, help_text='Leave empty to use latest version.', null=True)),
                ('composite', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sentinel.Composite')),
            ],
        ),
        migrations.CreateModel(
            name='MGRSTile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('utm_zone', models.CharField(max_length=2)),
                ('latitude_band', models.CharField(max_length=1)),
                ('grid_square', models.CharField(max_length=2)),
                ('geom', django.contrib.gis.db.models.fields.PolygonField(null=True, srid=4326)),
            ],
        ),
        migrations.CreateModel(
            name='SentinelTile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('prefix', models.TextField(unique=True)),
                ('datastrip', models.TextField()),
                ('product_name', models.TextField()),
                ('tile_geom', django.contrib.gis.db.models.fields.PolygonField(null=True, srid=4326)),
                ('tile_data_geom', django.contrib.gis.db.models.fields.MultiPolygonField(null=True, srid=4326)),
                ('collected', models.DateTimeField()),
                ('cloudy_pixel_percentage', models.FloatField()),
                ('data_coverage_percentage', models.FloatField()),
                ('angle_azimuth', models.FloatField(default=0)),
                ('angle_altitude', models.FloatField(default=0)),
                ('level', models.CharField(choices=[('l1c', 'Level 1C'), ('l2a', 'Level 2A')], default='l1c', max_length=10)),
                ('status', models.CharField(choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Processing', 'Processing'), ('Finished', 'Finished'), ('Failed', 'Failed')], default='Unprocessed', max_length=20)),
                ('log', models.TextField(blank=True, default='')),
                ('mgrstile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sentinel.MGRSTile')),
            ],
        ),
        migrations.CreateModel(
            name='SentinelTileAggregationLayer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('active', models.BooleanField(default=True)),
                ('aggregationlayer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='raster_aggregation.AggregationLayer')),
                ('sentineltile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sentinel.SentinelTile')),
            ],
        ),
        migrations.CreateModel(
            name='SentinelTileBand',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('band', models.CharField(choices=[('B01.jp2', 'Band 1 - Coastal aerosol, WL 0.443 mu, RES 60 m'), ('B02.jp2', 'Band 2 - Blue, WL 0.490 mu, RES 10 m'), ('B03.jp2', 'Band 3 - Green, WL 0.560 mu, RES 10 m'), ('B04.jp2', 'Band 4 - Red WL 0.665 mu, RES 10m'), ('B05.jp2', 'Band 5 - Vegetation Red Edge, WL 0.705, RES 20 m'), ('B06.jp2', 'Band 6 - Vegetation Red Edge, WL 0.740, RES 20 m'), ('B07.jp2', 'Band 7 - Vegetation Red Edge, WL 0.783, RES 20 m'), ('B08.jp2', 'Band 8 - NIR, WL 0.842, RES 10 m'), ('B8A.jp2', 'Band 8A - Vegetation Red Edge, WL 0.865, RES 20 m'), ('B09.jp2', 'Band 9 - Water vapour, WL 0.945, RES 60 m'), ('B10.jp2', 'Band 10 - SWIR - Cirrus, WL 1.375, RES 60 m'), ('B11.jp2', 'Band 11 - SWIR, WL 1.610, RES 20 m'), ('B12.jp2', 'Band 12 - SWIR, WL 2.190, RES 20 m')], max_length=7)),
                ('layer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='raster.RasterLayer')),
                ('tile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sentinel.SentinelTile')),
            ],
        ),
        migrations.CreateModel(
            name='SentinelTileSceneClass',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('layer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='raster.RasterLayer')),
                ('tile', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='sentinel.SentinelTile')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='mgrstile',
            unique_together={('utm_zone', 'latitude_band', 'grid_square')},
        ),
        migrations.AddField(
            model_name='compositebuild',
            name='compositetiles',
            field=models.ManyToManyField(to='sentinel.CompositeTile'),
        ),
        migrations.AddField(
            model_name='compositebuild',
            name='owner',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='compositebuild',
            name='sentineltiles',
            field=models.ManyToManyField(to='sentinel.SentinelTile'),
        ),
        migrations.AddField(
            model_name='composite',
            name='sentineltiles',
            field=models.ManyToManyField(blank=True, help_text='Limit the composite to a specific set of sentinel tiles.', to='sentinel.SentinelTile'),
        ),
        migrations.AlterUniqueTogether(
            name='sentineltileband',
            unique_together={('tile', 'band')},
        ),
        migrations.AlterUniqueTogether(
            name='sentineltileaggregationlayer',
            unique_together={('sentineltile', 'aggregationlayer')},
        ),
        migrations.AlterUniqueTogether(
            name='compositetile',
            unique_together={('composite', 'tilez', 'tilex', 'tiley')},
        ),
        migrations.AlterUniqueTogether(
            name='compositeband',
            unique_together={('composite', 'band')},
        ),
    ]
