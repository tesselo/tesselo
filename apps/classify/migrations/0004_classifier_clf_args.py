# Generated by Django 2.0.5 on 2018-10-09 14:59

import django.contrib.postgres.fields.hstore
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0003_auto_20181008_1323'),
    ]

    operations = [
        migrations.AddField(
            model_name='classifier',
            name='clf_args',
            field=django.contrib.postgres.fields.hstore.HStoreField(default={}, help_text='Keyword Arguments passed to the classifier.'),
        ),
    ]
