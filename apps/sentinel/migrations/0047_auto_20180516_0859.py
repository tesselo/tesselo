# Generated by Django 2.0.2 on 2018-05-16 08:59

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0046_sentineltilesceneclass'),
    ]

    operations = [
        migrations.AlterField(
            model_name='bucketparselog',
            name='log',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='compositebuild',
            name='log',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='compositetile',
            name='log',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AlterField(
            model_name='sentineltile',
            name='log',
            field=models.TextField(blank=True, default=''),
        ),
    ]
