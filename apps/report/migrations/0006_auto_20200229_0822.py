# Generated by Django 2.1.7 on 2020-02-29 08:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('report', '0005_reportschedule_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='reportaggregation',
            name='max_date',
            field=models.DateField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='reportaggregation',
            name='min_date',
            field=models.DateField(blank=True, editable=False, null=True),
        ),
    ]