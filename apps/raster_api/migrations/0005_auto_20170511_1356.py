# -*- coding: utf-8 -*-
# Generated by Django 1.11.2 on 2017-05-11 13:56
from __future__ import unicode_literals

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0008_alter_user_username_max_length'),
        ('raster', '0038_merge_20170509_1003'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('raster_api', '0004_publiclegend'),
    ]

    operations = [
        migrations.CreateModel(
            name='LegendSemanticsGroupObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='raster.Legend')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Group')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='LegendSemanticsUserObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='raster.Legend')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PublicLegendSemantics',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public', models.BooleanField(default=False)),
                ('legendsemantics', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='raster.LegendSemantics')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='legendsemanticsuserobjectpermission',
            unique_together=set([('user', 'permission', 'content_object')]),
        ),
        migrations.AlterUniqueTogether(
            name='legendsemanticsgroupobjectpermission',
            unique_together=set([('group', 'permission', 'content_object')]),
        ),
    ]
