# Generated by Django 3.0.5 on 2020-05-25 08:22

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('sentinel', '0014_auto_20200515_1641'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='compositebuild',
            options={'ordering': ['composite__min_date']},
        ),
    ]
