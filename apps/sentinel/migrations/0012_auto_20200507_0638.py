# Generated by Django 3.0.5 on 2020-05-07 06:38

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0011_auto_20200409_1934'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='compositebuild',
            name='owner',
        ),
        migrations.RemoveField(
            model_name='compositebuildschedule',
            name='owner',
        ),
    ]