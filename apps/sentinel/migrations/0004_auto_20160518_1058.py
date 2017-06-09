# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2016-05-18 10:58
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0003_auto_20160510_0541'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sentineltileband',
            name='band',
            field=models.CharField(choices=[('B01.jp2', 'Band 1 - Coastal aerosol, WL 0.443 mu, RES 60 m'), ('B02.jp2', 'Band 2 - Blue, WL 0.490 mu, RES 10 m'), ('B03.jp2', 'Band 3 - Green, WL 0.560 mu, RES 10 m'), ('B04.jp2', 'Band 4 - Red WL 0.665 mu, RES 10m'), ('B05.jp2', 'Band 5 - Vegetation Red Edge, WL 0.705, RES 20 m'), ('B06.jp2', 'Band 6 - Vegetation Red Edge, WL 0.740, RES 20 m'), ('B07.jp2', 'Band 7 - Vegetation Red Edge, WL 0.783, RES 20 m'), ('B08.jp2', 'Band 8 - NIR, WL 0.842, RES 10 m'), ('B8A.jp2', 'Band 8A - Vegetation Red Edge, WL 0.865, RES 20 m'), ('B09.jp2', 'Band 9 - Water vapour, WL 0.945, RES 60 m'), ('B10.jp2', 'Band 10 - SWIR - Cirrus, WL 1.375, RES 60 m'), ('B11.jp2', 'Band 11 - SWIR, WL 1.610, RES 20 m'), ('B12.jp2', 'Band 12 - SWIR, WL 2.190, RES 20 m')], max_length=7),
        ),
    ]
