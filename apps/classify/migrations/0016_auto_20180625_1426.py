# Generated by Django 2.0.2 on 2018-06-25 14:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0015_auto_20180625_1302'),
    ]

    operations = [
        migrations.AddField(
            model_name='predictedlayer',
            name='status',
            field=models.CharField(choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Processing', 'Processing'), ('Finished', 'Finished'), ('Failed', 'Failed')], default='Unprocessed', max_length=20),
        ),
        migrations.AlterField(
            model_name='predictedlayer',
            name='log',
            field=models.TextField(blank=True, default=''),
        ),
    ]