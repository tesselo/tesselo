# Generated by Django 2.0.5 on 2018-10-24 12:04

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0004_auto_20181023_0839'),
        ('classify', '0006_classifier_needs_large_instance'),
    ]

    operations = [
        migrations.AddField(
            model_name='classifieraccuracy',
            name='rsquared',
            field=models.FloatField(default=0),
        ),
        migrations.AddField(
            model_name='traininglayer',
            name='continuous',
            field=models.BooleanField(default=False, help_text='Are the target values of this traininglayer continuous values? If false, its assumed to be discrete.'),
        ),
        migrations.AddField(
            model_name='traininglayerexport',
            name='composite',
            field=models.ForeignKey(blank=True, help_text='Is used as export data source if specified. If left blank, the original traininglayer pixels are exported.', null=True, on_delete=django.db.models.deletion.SET_NULL, to='sentinel.Composite'),
        ),
        migrations.AddField(
            model_name='traininglayerexport',
            name='sentineltile',
            field=models.ForeignKey(blank=True, help_text='Is used as export data source if specified. If left blank, the original traininglayer pixels are exported.', null=True, on_delete=django.db.models.deletion.SET_NULL, to='sentinel.SentinelTile'),
        ),
        migrations.AlterField(
            model_name='classifier',
            name='algorithm',
            field=models.CharField(choices=[('svm', 'Support Vector Machines'), ('lsvm', 'Linear Support Vector Machines'), ('rf', 'Random Forest'), ('nn', 'Neural Network'), ('svr', 'Support Vector Machines Regressor'), ('lsvr', 'Linear Support Vector Machines Regressor'), ('rfr', 'Random Forest Regressor'), ('nnr', 'Neural Network Regressor')], max_length=10),
        ),
        migrations.AlterField(
            model_name='classifier',
            name='sentineltile',
            field=models.ForeignKey(blank=True, help_text='Is used as training data source if specified. If left blank, the original traininglayer pixels are used.', null=True, on_delete=django.db.models.deletion.SET_NULL, to='sentinel.SentinelTile'),
        ),
        migrations.AlterField(
            model_name='traininglayerexport',
            name='data',
            field=models.FileField(blank=True, null=True, upload_to='clouds/traininglayer_exports'),
        ),
        migrations.AlterField(
            model_name='trainingsample',
            name='category',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
        migrations.AlterField(
            model_name='trainingsample',
            name='value',
            field=models.FloatField(),
        ),
    ]
