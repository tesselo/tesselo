# Generated by Django 2.1.7 on 2019-03-11 12:22

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0013_auto_20190311_1208'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='classifier',
            name='composite',
        ),
    ]