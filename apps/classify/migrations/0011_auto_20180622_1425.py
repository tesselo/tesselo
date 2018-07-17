# Generated by Django 2.0.2 on 2018-06-22 14:11

from django.db import migrations


def move_trainingsamples_to_traininglayer(apps, schema_editor):
    TrainingSample = apps.get_model("classify", "TrainingSample")
    TrainingLayer = apps.get_model("classify", "TrainingLayer")
    Classifier = apps.get_model("classify", "Classifier")

    for clf in Classifier.objects.all():
        # Create a training layer for this classifier if necessary.
        if not clf.traininglayer:
            clf.traininglayer = TrainingLayer.objects.create(name=clf.name)
            clf.save()

        # Assign training sample to training layer for this classifier.
        for sample in clf.trainingsamples.all():
            sample.traininglayer = clf.traininglayer
            sample.save()

    # Remove "free floating" training samples.
    TrainingSample.objects.filter(classifier__isnull=True).delete()


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0010_auto_20180622_1411'),
    ]

    operations = [
        migrations.RunPython(move_trainingsamples_to_traininglayer, reverse),
    ]