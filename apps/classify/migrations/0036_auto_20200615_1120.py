# Generated by Django 3.0.7 on 2020-06-15 11:20

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0035_classifier_needs_gpu_instance'),
    ]

    operations = [
        migrations.AddField(
            model_name='predictedlayer',
            name='sieve_connectivity',
            field=models.IntegerField(choices=[(4, 4), (8, 8)], default=4),
        ),
        migrations.AddField(
            model_name='predictedlayer',
            name='sieve_parent',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='classify.PredictedLayer'),
        ),
        migrations.AddField(
            model_name='predictedlayer',
            name='sieve_threshold',
            field=models.IntegerField(default=0),
        ),
    ]
