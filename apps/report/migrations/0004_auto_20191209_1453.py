# Generated by Django 2.1.7 on 2019-12-09 14:53

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('report', '0003_auto_20191031_1130'),
    ]

    operations = [
        migrations.AddField(
            model_name='reportschedule',
            name='active',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='reportscheduletask',
            name='aggregationlayer',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='raster_aggregation.AggregationLayer'),
        ),
        migrations.AlterField(
            model_name='reportscheduletask',
            name='composite',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='sentinel.Composite'),
        ),
        migrations.AlterField(
            model_name='reportscheduletask',
            name='formula',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='formulary.Formula'),
        ),
        migrations.AlterField(
            model_name='reportscheduletask',
            name='log',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='reportscheduletask',
            name='predictedlayer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='classify.PredictedLayer'),
        ),
        migrations.AlterField(
            model_name='reportscheduletask',
            name='status',
            field=models.CharField(choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Processing', 'Processing'), ('Finished', 'Finished'), ('Failed', 'Failed')], default='Unprocessed', max_length=20),
        ),
    ]
