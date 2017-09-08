# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-06-15 21:01
from __future__ import unicode_literals

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0021_auto_20170615_2116'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('auth', '0008_alter_user_username_max_length'),
        ('raster_api', '0011_create_perms_tables'),
    ]

    operations = [
        migrations.CreateModel(
            name='PublicWorldLayerGroup',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public', models.BooleanField(default=False)),
                ('worldlayergroup', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='sentinel.WorldLayerGroup')),
            ],
        ),
        migrations.CreateModel(
            name='WorldLayerGroupGroupObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sentinel.WorldLayerGroup')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Group')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='WorldLayerGroupUserObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='sentinel.WorldLayerGroup')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AlterUniqueTogether(
            name='worldlayergroupuserobjectpermission',
            unique_together=set([('user', 'permission', 'content_object')]),
        ),
        migrations.AlterUniqueTogether(
            name='worldlayergroupgroupobjectpermission',
            unique_together=set([('group', 'permission', 'content_object')]),
        ),
    ]
