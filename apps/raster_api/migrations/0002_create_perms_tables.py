# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations


def create_custom_permissions(apps, schema_editor):

    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    for modelname in ('RasterLayer', 'Legend', 'LegendSemantics',
                      'AggregationLayer', 'ValueCountResult'):

        if modelname in ('AggregationLayer', 'ValueCountResult', ):
            model = apps.get_model("raster_aggregation", modelname)
        else:
            model = apps.get_model("raster", modelname)

        content_type = ContentType.objects.get_for_model(model)

        for action in ('view', ):

            perm = Permission.objects.filter(
                codename='{action}_{model}'.format(action=action, model=modelname.lower()),
                content_type=content_type,
            ).first()

            if not perm:
                Permission.objects.create(
                    codename='{action}_{model}'.format(action=action, model=modelname.lower()),
                    name='Can {action} {model}'.format(action=action, model=modelname),
                    content_type=content_type,
                )


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('raster_api', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_custom_permissions, reverse),
    ]
