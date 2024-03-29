# Generated by Django 2.1.7 on 2019-10-30 11:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('report', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='reportschedule',
            name='log',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='reportschedule',
            name='status',
            field=models.CharField(choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Processing', 'Processing'), ('Finished', 'Finished'), ('Failed', 'Failed')], default='Unprocessed', max_length=20),
        ),
    ]
