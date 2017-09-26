# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-09-25 16:53
from __future__ import unicode_literals

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sentinel', '0026_auto_20170925_1653'),
        ('auth', '0008_alter_user_username_max_length'),
        ('raster_api', '0016_auto_20170925_1653'),
    ]

    operations = [
        migrations.AddField(
            model_name='sentineltileaggregationlayeruserobjectpermission',
            name='content_object',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sentinel.SentinelTileAggregationLayer'),
        ),
        migrations.AddField(
            model_name='sentineltileaggregationlayeruserobjectpermission',
            name='permission',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission'),
        ),
        migrations.AddField(
            model_name='sentineltileaggregationlayeruserobjectpermission',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='sentineltileaggregationlayergroupobjectpermission',
            name='content_object',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sentinel.SentinelTileAggregationLayer'),
        ),
        migrations.AddField(
            model_name='sentineltileaggregationlayergroupobjectpermission',
            name='group',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Group'),
        ),
        migrations.AddField(
            model_name='sentineltileaggregationlayergroupobjectpermission',
            name='permission',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission'),
        ),
        migrations.AddField(
            model_name='publicsentineltileaggregationlayer',
            name='sentineltileaggregationlayer',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='sentinel.SentinelTileAggregationLayer'),
        ),
        migrations.AlterUniqueTogether(
            name='sentineltileaggregationlayeruserobjectpermission',
            unique_together=set([('user', 'permission', 'content_object')]),
        ),
        migrations.AlterUniqueTogether(
            name='sentineltileaggregationlayergroupobjectpermission',
            unique_together=set([('group', 'permission', 'content_object')]),
        ),
    ]