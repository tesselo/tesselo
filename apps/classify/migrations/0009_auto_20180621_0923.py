# Generated by Django 2.0.2 on 2018-06-21 09:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0008_remove_predictedlayer_created'),
    ]

    operations = [
        migrations.AddField(
            model_name='predictedlayer',
            name='chunks_count',
            field=models.IntegerField(blank=True, default=0),
        ),
        migrations.AddField(
            model_name='predictedlayer',
            name='chunks_done',
            field=models.IntegerField(blank=True, default=0),
        ),
    ]
