# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-01-25 09:07
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0030_auto_20180110_1857'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='WorldParseProcess',
            new_name='CompositeBuildLog',
        ),
    ]