# Generated by Django 2.2.9 on 2020-04-07 08:21

import django.contrib.postgres.fields.hstore
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('raster_api', '0005_tesselouseraccount_profile'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tesselouseraccount',
            name='profile',
            field=django.contrib.postgres.fields.hstore.HStoreField(blank=True, default=dict),
        ),
    ]
