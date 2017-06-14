# -*- coding: utf-8 -*-
# Generated by Django 1.10.4.dev20161124100321 on 2016-11-28 10:44
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0013_auto_20161012_1003'),
    ]

    operations = [
        migrations.CreateModel(
            name='WorldLayerGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=500)),
                ('all_zones', models.BooleanField(default=False, help_text='If checked, this layer will be built for all zones of interest.')),
                ('min_date', models.DateField()),
                ('max_date', models.DateField()),
                ('active', models.BooleanField(default=True, help_text='If unchecked, this area will not be included in the parsing.')),
                ('last_built', models.DateTimeField(blank=True, null=True)),
                ('currently_building', models.BooleanField(default=False)),
                ('worldlayers', models.ManyToManyField(to='sentinel.WorldLayer')),
                ('zonesofinterest', models.ManyToManyField(help_text='What zones should this layer be built for?', to='sentinel.ZoneOfInterest')),
            ],
        ),
    ]