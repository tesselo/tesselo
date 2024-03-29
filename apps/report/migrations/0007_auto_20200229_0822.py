# Generated by Django 2.1.7 on 2020-02-29 08:22

from django.db import migrations
from django.db.models import OuterRef, Subquery


def forward(apps, schema_editor):
    ReportAggregation = apps.get_model("report", "ReportAggregation")

    sq = Subquery(ReportAggregation.objects.filter(id=OuterRef('id'), composite__isnull=False).values('composite__min_date')[:1])
    ReportAggregation.objects.filter(composite__isnull=False).update(min_date=sq)

    sq = Subquery(ReportAggregation.objects.filter(id=OuterRef('id'), composite__isnull=False).values('composite__max_date')[:1])
    ReportAggregation.objects.filter(composite__isnull=False).update(max_date=sq)

    sq = Subquery(ReportAggregation.objects.filter(id=OuterRef('id'), predictedlayer__isnull=False).values('predictedlayer__min_date')[:1])
    ReportAggregation.objects.filter(predictedlayer__isnull=False).update(min_date=sq)

    sq = Subquery(ReportAggregation.objects.filter(id=OuterRef('id'), predictedlayer__isnull=False).values('predictedlayer__max_date')[:1])
    ReportAggregation.objects.filter(predictedlayer__isnull=False).update(max_date=sq)


def backward(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('report', '0006_auto_20200229_0822'),
        ('classify', '0030_auto_20200228_1417'),
    ]

    operations = [
        migrations.RunPython(forward, backward)
    ]
