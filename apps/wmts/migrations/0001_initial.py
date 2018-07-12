# Generated by Django 2.0.2 on 2018-07-12 13:27

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0009_alter_user_last_name_max_length'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sentinel', '0050_compositetile_cloud_version'),
        ('formulary', '0007_auto_20180712_1135'),
    ]

    operations = [
        migrations.CreateModel(
            name='PublicWMTSLayer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('public', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='WMTSLayer',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=200)),
                ('composite', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='sentinel.Composite')),
                ('formula', models.ForeignKey(blank=True, help_text='Assumes RGB mode if left blank.', null=True, on_delete=django.db.models.deletion.CASCADE, to='formulary.Formula')),
                ('sentineltile', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='sentinel.SentinelTile')),
            ],
            options={
                'permissions': (('view_wmtslayer', 'View WMTS layer'),),
            },
        ),
        migrations.CreateModel(
            name='WMTSLayerGroupObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wmts.WMTSLayer')),
                ('group', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Group')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='WMTSLayerUserObjectPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content_object', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='wmts.WMTSLayer')),
                ('permission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.Permission')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='publicwmtslayer',
            name='wmtslayer',
            field=models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to='wmts.WMTSLayer'),
        ),
        migrations.AlterUniqueTogether(
            name='wmtslayeruserobjectpermission',
            unique_together={('user', 'permission', 'content_object')},
        ),
        migrations.AlterUniqueTogether(
            name='wmtslayergroupobjectpermission',
            unique_together={('group', 'permission', 'content_object')},
        ),
    ]
