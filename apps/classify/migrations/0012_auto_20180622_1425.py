# Generated by Django 2.0.2 on 2018-06-22 14:25

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0011_auto_20180622_1425'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='classifier',
            name='trainingsamples',
        ),
        migrations.AlterField(
            model_name='trainingsample',
            name='traininglayer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classify.TrainingLayer'),
        ),
    ]
