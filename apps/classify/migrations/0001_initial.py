# Generated by Django 2.0.2 on 2018-09-25 14:18

from django.conf import settings
import django.contrib.gis.db.models.fields
import django.contrib.postgres.fields
import django.contrib.postgres.fields.hstore
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('sentinel', '__first__'),
        ('auth', '0009_alter_user_last_name_max_length'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('raster_aggregation', '0020_auto_20180308_0435'),
        ('raster', '0039_merge_20171116_1051'),
    ]

    operations = [
        migrations.CreateModel(
            name='Classifier',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('algorithm', models.CharField(choices=[('svm', 'Support Vector Machines'), ('rf', 'Random Forest'), ('nn', 'Neural Network')], max_length=10)),
                ('trained', models.FileField(blank=True, null=True, upload_to='clouds/classifiers')),
                ('splitfraction', models.FloatField(default=0, help_text='Fraction of pixels that should be reserved for validation.')),
                ('band_names', models.CharField(default='B01,B02,B03,B04,B05,B06,B07,B08,B8A,B09,B11,B12', help_text='Comma-separated list of band names and layer ids. If an integer value is added, it is assumed to be a rasterlayer id that should be included in the export.', max_length=500)),
                ('status', models.CharField(choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Processing', 'Processing'), ('Finished', 'Finished'), ('Failed', 'Failed')], default='Unprocessed', max_length=20)),
                ('log', models.TextField(blank=True, default='')),
            ],
        ),
        migrations.CreateModel(
            name='ClassifierAccuracy',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('accuracy_matrix', django.contrib.postgres.fields.ArrayField(base_field=django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), default=[], size=None), default=[], size=None)),
                ('cohen_kappa', models.FloatField(default=0)),
                ('accuracy_score', models.FloatField(default=0)),
                ('classifier', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='classify.Classifier')),
            ],
        ),
        migrations.CreateModel(
            name='ClassifierGroupObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classify.Classifier')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Group')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ClassifierUserObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classify.Classifier')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PredictedLayer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('log', models.TextField(blank=True, default='')),
                ('status', models.CharField(choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Processing', 'Processing'), ('Finished', 'Finished'), ('Failed', 'Failed')], default='Unprocessed', max_length=20)),
                ('aggregationlayer', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='raster_aggregation.AggregationLayer')),
                ('classifier', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='classify.Classifier')),
                ('composite', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sentinel.Composite')),
                ('rasterlayer', models.ForeignKey(blank=True, on_delete=django.db.models.deletion.CASCADE, to='raster.RasterLayer')),
                ('sentineltile', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='sentinel.SentinelTile')),
            ],
        ),
        migrations.CreateModel(
            name='PredictedLayerChunk',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('from_index', models.IntegerField()),
                ('to_index', models.IntegerField()),
                ('status', models.CharField(choices=[('Unprocessed', 'Unprocessed'), ('Pending', 'Pending'), ('Processing', 'Processing'), ('Finished', 'Finished'), ('Failed', 'Failed')], default='Unprocessed', max_length=100)),
                ('predictedlayer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classify.PredictedLayer')),
            ],
        ),
        migrations.CreateModel(
            name='PredictedLayerGroupObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classify.PredictedLayer')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Group')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PredictedLayerUserObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classify.PredictedLayer')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PublicClassifier',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public', models.BooleanField(default=False)),
                ('classifier', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='classify.Classifier')),
            ],
        ),
        migrations.CreateModel(
            name='PublicPredictedLayer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public', models.BooleanField(default=False)),
                ('predictedlayer', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='classify.PredictedLayer')),
            ],
        ),
        migrations.CreateModel(
            name='PublicTrainingLayer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='PublicTrainingSample',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='TrainingLayer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=500)),
                ('legend', django.contrib.postgres.fields.hstore.HStoreField(default={}, editable=False)),
            ],
            options={
                'permissions': (('view_traininglayer', 'View training layer'),),
            },
        ),
        migrations.CreateModel(
            name='TrainingLayerExport',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('data', models.FileField(upload_to='clouds/traininglayer_exports')),
                ('created', models.DateTimeField(auto_now=True)),
                ('traininglayer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classify.TrainingLayer')),
            ],
        ),
        migrations.CreateModel(
            name='TrainingLayerGroupObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classify.TrainingLayer')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Group')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TrainingLayerUserObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classify.TrainingLayer')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TrainingSample',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('geom', django.contrib.gis.db.models.fields.PolygonField(srid=4326)),
                ('category', models.CharField(max_length=100)),
                ('value', models.IntegerField()),
                ('composite', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='sentinel.Composite')),
                ('sentineltile', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='sentinel.SentinelTile')),
                ('traininglayer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classify.TrainingLayer')),
            ],
        ),
        migrations.CreateModel(
            name='TrainingSampleGroupObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classify.TrainingSample')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Group')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TrainingSampleUserObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='classify.TrainingSample')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='publictrainingsample',
            name='trainingsample',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='classify.TrainingSample'),
        ),
        migrations.AddField(
            model_name='publictraininglayer',
            name='traininglayer',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='classify.TrainingLayer'),
        ),
        migrations.AddField(
            model_name='classifier',
            name='traininglayer',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='classify.TrainingLayer'),
        ),
        migrations.AlterUniqueTogether(
            name='trainingsampleuserobjectpermission',
            unique_together={('user', 'permission', 'content_object')},
        ),
        migrations.AlterUniqueTogether(
            name='trainingsamplegroupobjectpermission',
            unique_together={('group', 'permission', 'content_object')},
        ),
        migrations.AlterUniqueTogether(
            name='traininglayeruserobjectpermission',
            unique_together={('user', 'permission', 'content_object')},
        ),
        migrations.AlterUniqueTogether(
            name='traininglayergroupobjectpermission',
            unique_together={('group', 'permission', 'content_object')},
        ),
        migrations.AlterUniqueTogether(
            name='predictedlayeruserobjectpermission',
            unique_together={('user', 'permission', 'content_object')},
        ),
        migrations.AlterUniqueTogether(
            name='predictedlayergroupobjectpermission',
            unique_together={('group', 'permission', 'content_object')},
        ),
        migrations.AlterUniqueTogether(
            name='classifieruserobjectpermission',
            unique_together={('user', 'permission', 'content_object')},
        ),
        migrations.AlterUniqueTogether(
            name='classifiergroupobjectpermission',
            unique_together={('group', 'permission', 'content_object')},
        ),
    ]
