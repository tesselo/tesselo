# Generated by Django 2.0.5 on 2018-10-26 13:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0004_auto_20181023_0839'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sentineltile',
            name='cloudy_pixel_percentage',
            field=models.FloatField(db_index=True),
        ),
        migrations.AlterField(
            model_name='sentineltile',
            name='collected',
            field=models.DateTimeField(db_index=True),
        ),
        migrations.AlterField(
            model_name='sentineltile',
            name='prefix',
            field=models.TextField(db_index=True, unique=True),
        ),
        migrations.AlterField(
            model_name='sentineltile',
            name='status',
            field=models.CharField(choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Processing', 'Processing'), ('Finished', 'Finished'), ('Failed', 'Failed'), ('Broken', 'Broken')], db_index=True, default='Unprocessed', max_length=20),
        ),
    ]
