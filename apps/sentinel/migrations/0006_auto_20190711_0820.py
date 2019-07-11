# Generated by Django 2.1.7 on 2019-07-11 08:20

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('sentinel', '0005_auto_20181026_1300'),
    ]

    operations = [
        migrations.CreateModel(
            name='CompositeBuildSchedule',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=150)),
                ('description', models.TextField(blank=True, default='')),
                ('active', models.BooleanField(default=True)),
                ('interval', models.CharField(blank=True, choices=[('Daily', 'Daily'), ('Weekly', 'Weekly'), ('Montly', 'Montly')], default='Montly', max_length=50)),
                ('log', models.TextField(blank=True, default='')),
                ('delay_build_days', models.IntegerField(default=0, help_text='Optinally delay the build of the interval by N days, to ensure internal registration of latest scenes.')),
                ('compositebuilds', models.ManyToManyField(to='sentinel.CompositeBuild')),
                ('owner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterModelOptions(
            name='composite',
            options={'ordering': ['min_date']},
        ),
    ]
