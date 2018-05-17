# Generated by Django 2.0.2 on 2018-05-17 12:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0047_auto_20180516_0859'),
    ]

    operations = [
        migrations.AlterField(
            model_name='compositebuild',
            name='status',
            field=models.CharField(blank=True, choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Ingesting Scenes', 'Ingesting Scenes'), ('Building Composite Tiles', 'Building Composite Tiles'), ('Finished', 'Finished'), ('Failed', 'Failed')], default='Unprocessed', max_length=50),
        ),
    ]
