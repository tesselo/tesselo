# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-12-05 09:37
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0027_sentineltile_level'),
    ]

    operations = [
        migrations.AddField(
            model_name='worldparseprocess',
            name='log',
            field=models.TextField(default=''),
        ),
    ]