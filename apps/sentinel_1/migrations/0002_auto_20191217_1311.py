# Generated by Django 2.1.7 on 2019-12-17 13:11

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('raster', '0040_merge_20190313_1143'),
        ('sentinel_1', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Sentinel1TileBand',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('band', models.CharField(choices=[('VV', 'VV Polarization'), ('VH', 'VH Polarization'), ('HH', 'HH Polarization'), ('HV', 'HV Polarization')], max_length=7)),
                ('layer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='raster.RasterLayer')),
            ],
        ),
        migrations.AddField(
            model_name='sentinel1tile',
            name='log',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='sentinel1tile',
            name='status',
            field=models.CharField(choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Processing', 'Processing'), ('Finished', 'Finished'), ('Failed', 'Failed'), ('Broken', 'Broken')], db_index=True, default='Unprocessed', max_length=20),
        ),
        migrations.AddField(
            model_name='sentinel1tileband',
            name='tile',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sentinel_1.Sentinel1Tile'),
        ),
        migrations.AlterUniqueTogether(
            name='sentinel1tileband',
            unique_together={('tile', 'band')},
        ),
    ]
