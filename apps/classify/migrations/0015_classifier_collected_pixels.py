# Generated by Django 2.1.7 on 2019-03-13 11:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0014_remove_classifier_composite'),
    ]

    operations = [
        migrations.AddField(
            model_name='classifier',
            name='collected_pixels',
            field=models.FileField(blank=True, null=True, upload_to='clouds/classifiers'),
        ),
    ]
