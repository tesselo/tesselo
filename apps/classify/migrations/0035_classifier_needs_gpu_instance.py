# Generated by Django 3.0.5 on 2020-06-13 07:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0034_trainingpixels_patch_size'),
    ]

    operations = [
        migrations.AddField(
            model_name='classifier',
            name='needs_gpu_instance',
            field=models.BooleanField(default=False),
        ),
    ]
