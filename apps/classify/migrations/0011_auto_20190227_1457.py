# Generated by Django 2.1.7 on 2019-02-27 14:57

import django.contrib.postgres.fields
import django.contrib.postgres.fields.hstore
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0010_auto_20190222_1503'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classifieraccuracy',
            name='accuracy_matrix',
            field=django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), default=list, size=None), default=list, size=None),
        ),
        migrations.AlterField(
            model_name='traininglayer',
            name='legend',
            field=django.contrib.postgres.fields.hstore.HStoreField(default=dict, editable=False),
        ),
    ]
