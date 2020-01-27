# Generated by Django 2.1.7 on 2020-01-21 14:48
from django.db import migrations


def forward(apps, schema_editor):
    PredictedLayer = apps.get_model("classify", "PredictedLayer")
    for lyr in PredictedLayer.objects.all():
        lyr.composites.add(lyr.composite)


def backward(apps, schema_editor):
    PredictedLayer = apps.get_model("classify", "PredictedLayer")
    for lyr in PredictedLayer.objects.all():
        lyr.composite = lyr.composites.first()
        lyr.save()


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0023_auto_20200121_1448'),
    ]

    operations = [
        migrations.RunPython(forward, backward)
    ]