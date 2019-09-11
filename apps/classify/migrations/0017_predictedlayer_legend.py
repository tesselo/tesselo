# Generated by Django 2.1.7 on 2019-09-04 12:50

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('raster', '0040_merge_20190313_1143'),
        ('classify', '0016_classifier_training_all_touched'),
    ]

    operations = [
        migrations.AddField(
            model_name='predictedlayer',
            name='legend',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='raster.Legend'),
        ),
    ]