# -*- coding: utf-8 -*-
# Generated by Django 1.9.8.dev20160616122412 on 2016-09-12 07:39
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0010_auto_20160912_0735'),
    ]

    operations = [
        migrations.RenameField(
            model_name='mgrstile',
            old_name='utmzone',
            new_name='utm_zone',
        ),
    ]
