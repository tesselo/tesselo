# Generated by Django 2.1.7 on 2020-02-07 10:39

import django.contrib.gis.db.models.fields
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel_1', '0002_auto_20191217_1311'),
    ]

    operations = [
        migrations.AddField(
            model_name='sentinel1tile',
            name='footprint_multi',
            field=django.contrib.gis.db.models.fields.MultiPolygonField(null=True, srid=4326),
        ),
    ]
