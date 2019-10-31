# Generated by Django 2.1.7 on 2019-10-31 11:30

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0018_auto_20190910_1121'),
        ('raster_aggregation', '0021_auto_20190905_0754'),
        ('formulary', '0003_auto_20190830_1649'),
        ('sentinel', '0007_compositebuildschedule_continuous_scene_ingestion'),
        ('report', '0002_auto_20191030_1122'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReportScheduleTask',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Processing', 'Processing'), ('Finished', 'Finished'), ('Failed', 'Failed')], default='Unprocessed', editable=False, max_length=20)),
                ('log', models.TextField(blank=True, default='', editable=False)),
                ('aggregationlayer', models.ForeignKey(editable=False, on_delete=django.db.models.deletion.CASCADE, to='raster_aggregation.AggregationLayer')),
                ('composite', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, to='sentinel.Composite')),
                ('formula', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, to='formulary.Formula')),
                ('predictedlayer', models.ForeignKey(blank=True, editable=False, null=True, on_delete=django.db.models.deletion.CASCADE, to='classify.PredictedLayer')),
            ],
        ),
        migrations.RemoveField(
            model_name='reportschedule',
            name='aggregationlayer',
        ),
        migrations.RemoveField(
            model_name='reportschedule',
            name='composite',
        ),
        migrations.RemoveField(
            model_name='reportschedule',
            name='formula',
        ),
        migrations.RemoveField(
            model_name='reportschedule',
            name='log',
        ),
        migrations.RemoveField(
            model_name='reportschedule',
            name='predictedlayer',
        ),
        migrations.RemoveField(
            model_name='reportschedule',
            name='status',
        ),
        migrations.AddField(
            model_name='reportschedule',
            name='aggregationlayers',
            field=models.ManyToManyField(to='raster_aggregation.AggregationLayer'),
        ),
        migrations.AddField(
            model_name='reportschedule',
            name='composites',
            field=models.ManyToManyField(to='sentinel.Composite'),
        ),
        migrations.AddField(
            model_name='reportschedule',
            name='formulas',
            field=models.ManyToManyField(to='formulary.Formula'),
        ),
        migrations.AddField(
            model_name='reportschedule',
            name='predictedlayers',
            field=models.ManyToManyField(to='classify.PredictedLayer'),
        ),
    ]
