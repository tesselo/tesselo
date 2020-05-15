# Generated by Django 3.0.5 on 2020-05-15 16:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0013_remove_composite_official'),
    ]

    operations = [
        migrations.AlterField(
            model_name='compositebuild',
            name='status',
            field=models.CharField(blank=True, choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Ingesting Scenes', 'Ingesting Scenes'), ('Building Composite Tiles', 'Building Composite Tiles'), ('Finished', 'Finished'), ('Failed', 'Failed'), ('Cleared', 'Cleared')], default='Unprocessed', max_length=50),
        ),
    ]
