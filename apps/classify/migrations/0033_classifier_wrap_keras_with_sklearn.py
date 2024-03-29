# Generated by Django 3.0.5 on 2020-05-30 06:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0032_auto_20200528_0612'),
    ]

    operations = [
        migrations.AddField(
            model_name='classifier',
            name='wrap_keras_with_sklearn',
            field=models.BooleanField(default=False, help_text='Wrap the keras models with a Sklearn Pipeline and RobustScaler. Ignored if not a Keras model.'),
        ),
    ]
