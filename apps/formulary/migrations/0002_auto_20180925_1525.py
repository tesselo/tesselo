# Generated by Django 2.0.2 on 2018-09-25 15:25

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('formulary', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='formula',
            options={'permissions': (('view_formula', 'View formula'),)},
        ),
    ]