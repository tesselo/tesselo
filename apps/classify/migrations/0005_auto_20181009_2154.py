# Generated by Django 2.0.5 on 2018-10-09 21:54

import django.contrib.postgres.fields.hstore
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0004_classifier_clf_args'),
    ]

    operations = [
        migrations.AlterField(
            model_name='classifier',
            name='clf_args',
            field=django.contrib.postgres.fields.hstore.HStoreField(blank=True, default={}, help_text='Keyword Arguments passed to the classifier.'),
        ),
    ]
