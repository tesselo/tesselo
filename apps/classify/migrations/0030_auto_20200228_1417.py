# Generated by Django 2.1.7 on 2020-02-28 14:17

from django.db import migrations
from django.db.models import Max, Min


def forward(apps, schema_editor):
    PredictedLayer = apps.get_model("classify", "PredictedLayer")
    for prd in PredictedLayer.objects.all():
        if prd.composites.count():
            prd.min_date = prd.composites.aggregate(Min('min_date'))['min_date__min']
            prd.max_date = prd.composites.aggregate(Max('max_date'))['max_date__max']
            prd.save()
        elif prd.sentineltile:
            prd.min_date = prd.sentineltile.collected.date()
            prd.max_date = prd.sentineltile.collected.date()
            prd.save()


def backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0029_auto_20200228_1118'),
    ]

    operations = [
        migrations.RunPython(forward, backward)
    ]
