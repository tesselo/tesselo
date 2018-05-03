from django.db import migrations


def create_custom_permissions(apps, schema_editor):

    Permission = apps.get_model("auth", "Permission")
    ContentType = apps.get_model("contenttypes", "ContentType")

    for modelname in ('PredictedLayer', ):

        model = apps.get_model("classify", modelname)

        content_type = ContentType.objects.get_for_model(model)

        for action in ('view', 'invite'):

            perm = Permission.objects.filter(
                codename='{action}_{model}'.format(action=action, model=modelname.lower()),
                content_type=content_type,
            ).first()

            if not perm:
                Permission.objects.create(
                    codename='{action}_{model}'.format(action=action, model=modelname.lower()),
                    name='Can {action} {model}'.format(action=action, model=modelname),
                    content_type=content_type,
                )


def reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('classify', '0006_auto_20180503_1353'),
    ]

    operations = [
        migrations.RunPython(create_custom_permissions, reverse),
    ]
