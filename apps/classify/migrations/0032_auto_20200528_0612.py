# Generated by Django 3.0.5 on 2020-05-28 06:12

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0031_auto_20200527_0701'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classifier',
            name='trainingpixels',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='classify.TrainingPixels'),
        ),
    ]