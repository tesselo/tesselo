# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2018-01-10 18:57
from __future__ import unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0029_auto_20180110_1851'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='WorldLayer',
            new_name='CompositeBand',
        ),
        migrations.RenameField(
            model_name='composite',
            old_name='worldlayers',
            new_name='compositebands',
        ),
        migrations.RenameField(
            model_name='worldparseprocess',
            old_name='worldlayergroup',
            new_name='composite',
        ),
    ]
