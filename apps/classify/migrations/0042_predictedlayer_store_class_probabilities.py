# Generated by Django 3.0.8 on 2021-03-29 11:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0041_trainingsample_attributes'),
    ]

    operations = [
        migrations.AddField(
            model_name='predictedlayer',
            name='store_class_probabilities',
            field=models.BooleanField(default=False),
        ),
    ]