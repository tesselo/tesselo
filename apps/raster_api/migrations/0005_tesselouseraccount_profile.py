# Generated by Django 2.1.7 on 2020-04-01 17:43

import django.contrib.postgres.fields.hstore
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('raster_api', '0004_readonlytoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='tesselouseraccount',
            name='profile',
            field=django.contrib.postgres.fields.hstore.HStoreField(default=dict),
        ),
    ]
