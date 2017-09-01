# -*- coding: utf-8 -*-
# Generated by Django 1.11.4 on 2017-07-14 09:09
from __future__ import unicode_literals

import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields.hstore
from django.db import migrations, models
import django.db.models.deletion
from django.contrib.postgres.operations import HStoreExtension


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('sentinel', '0022_sentineltile_tile_geom'),
    ]

    operations = [
        HStoreExtension(),
        migrations.CreateModel(
            name='Classifier',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('algorithm', models.CharField(choices=[('svm', 'Support Vector Machines'), ('rf', 'Random Forest'), ('nn', 'Neural Network')], max_length=10)),
                ('trained', models.FileField(blank=True, null=True, upload_to='clouds/classifiers')),
                ('legend', django.contrib.postgres.fields.hstore.HStoreField(default={})),
            ],
        ),
        migrations.CreateModel(
            name='TrainingSample',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geom', django.contrib.gis.db.models.fields.PolygonField(srid=4326)),
                ('category', models.CharField(max_length=100)),
                ('value', models.IntegerField()),
                ('sentineltile', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='sentinel.SentinelTile')),
                ('worldlayergroup', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='sentinel.WorldLayerGroup')),
            ],
        ),
        migrations.AddField(
            model_name='classifier',
            name='trainingsamples',
            field=models.ManyToManyField(to='classify.TrainingSample'),
        ),
    ]