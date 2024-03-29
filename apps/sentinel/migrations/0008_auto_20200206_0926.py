# Generated by Django 2.1.7 on 2020-02-06 09:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel_1', '0002_auto_20191217_1311'),
        ('sentinel', '0007_compositebuildschedule_continuous_scene_ingestion'),
    ]

    operations = [
        migrations.AddField(
            model_name='composite',
            name='sentinel1tiles',
            field=models.ManyToManyField(blank=True, help_text='Limit the composite to a specific set of sentinel-1 tiles.', to='sentinel_1.Sentinel1Tile'),
        ),
        migrations.AddField(
            model_name='compositebuild',
            name='include_sentinel_1',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='compositebuild',
            name='include_sentinel_2',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='compositebuild',
            name='sentinel1tiles',
            field=models.ManyToManyField(to='sentinel_1.Sentinel1Tile'),
        ),
        migrations.AddField(
            model_name='compositetile',
            name='include_sentinel_1',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='compositetile',
            name='include_sentinel_2',
            field=models.BooleanField(default=True),
        ),
    ]
