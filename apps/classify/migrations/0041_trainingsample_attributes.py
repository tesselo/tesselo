# Generated by Django 3.0.8 on 2020-10-09 15:24

import django.contrib.postgres.fields.hstore
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0040_trainingpixels_flatten'),
    ]

    operations = [
        migrations.AddField(
            model_name='trainingsample',
            name='attributes',
            field=django.contrib.postgres.fields.hstore.HStoreField(default=dict),
        ),
    ]
