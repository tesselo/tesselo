# Generated by Django 2.0.2 on 2018-02-20 14:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('raster_api', '0020_create_perms_tables'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='publiczoneofinterest',
            name='zoneofinterest',
        ),
        migrations.AlterUniqueTogether(
            name='zoneofinterestgroupobjectpermission',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='zoneofinterestgroupobjectpermission',
            name='content_object',
        ),
        migrations.RemoveField(
            model_name='zoneofinterestgroupobjectpermission',
            name='group',
        ),
        migrations.RemoveField(
            model_name='zoneofinterestgroupobjectpermission',
            name='permission',
        ),
        migrations.AlterUniqueTogether(
            name='zoneofinterestuserobjectpermission',
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name='zoneofinterestuserobjectpermission',
            name='content_object',
        ),
        migrations.RemoveField(
            model_name='zoneofinterestuserobjectpermission',
            name='permission',
        ),
        migrations.RemoveField(
            model_name='zoneofinterestuserobjectpermission',
            name='user',
        ),
        migrations.DeleteModel(
            name='PublicZoneOfInterest',
        ),
        migrations.DeleteModel(
            name='ZoneOfInterestGroupObjectPermission',
        ),
        migrations.DeleteModel(
            name='ZoneOfInterestUserObjectPermission',
        ),
    ]