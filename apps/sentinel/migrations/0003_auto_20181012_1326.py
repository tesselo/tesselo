# Generated by Django 2.0.5 on 2018-10-12 13:26

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0006_classifier_needs_large_instance'),
        ('sentinel', '0002_auto_20180925_1525'),
    ]

    operations = [
        migrations.AddField(
            model_name='compositebuild',
            name='cloud_classifier',
            field=models.ForeignKey(blank=True, help_text='Use a classifier based cloud removal. The classifier is assumed to return a cloud probability or rank (the higher the output the more likely its a cloud).', null=True, on_delete=django.db.models.deletion.SET_NULL, to='classify.Classifier'),
        ),
        migrations.AddField(
            model_name='compositetile',
            name='cloud_classifier',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='classify.Classifier'),
        ),
    ]