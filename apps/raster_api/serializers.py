import json

from raster.models import (
    Legend, LegendEntry, LegendSemantics, RasterLayer, RasterLayerBandMetadata, RasterLayerMetadata,
    RasterLayerParseStatus
)
from rest_framework.serializers import (
    CharField, IntegerField, ModelField, ModelSerializer, Serializer, SerializerMethodField
)

from django.contrib.auth.models import Group, User
from django.shortcuts import get_object_or_404
from guardian.shortcuts import get_perms


class UserSerializer(ModelSerializer):

    class Meta:
        model = User
        fields = ('id', 'username', )
        read_only_fields = ('id', 'username', )


class GroupSerializer(ModelSerializer):

    class Meta:
        model = Group
        fields = ('id', 'name', )
        read_only_fields = ('id', 'name', )


class PermissionSerializer(ModelSerializer):

    class Meta:
        model = Group
        fields = ('id', 'codename', )
        read_only_fields = ('id', 'name', )


class UserObjectPermissionSerializer(Serializer):

    id = IntegerField(source='user.id')
    username = CharField(source='user.username')
    permission = CharField(source='permission.codename')

    class Meta:
        fields = ('id', 'username', 'permission', )


class GroupObjectPermissionSerializer(Serializer):

    id = IntegerField(source='group.id')
    name = CharField(source='group.name')
    permission = CharField(source='permission.codename')

    class Meta:
        fields = ('id', 'username', 'permission', )


class PermissionsModelSerializer(ModelSerializer):

    permissions = SerializerMethodField()
    users = SerializerMethodField()
    groups = SerializerMethodField()
    public = SerializerMethodField(read_only=True)

    def __init__(self, *args, **kwargs):
        if hasattr(self.Meta, 'fields'):
            if 'permissions' not in self.Meta.fields:
                self.Meta.fields += ('permissions', )
            if 'public' not in self.Meta.fields:
                self.Meta.fields += ('public', )
            if 'users' not in self.Meta.fields:
                self.Meta.fields += ('users', )
            if 'groups' not in self.Meta.fields:
                self.Meta.fields += ('groups', )

        super(PermissionsModelSerializer, self).__init__(*args, **kwargs)

    def get_permissions(self, obj):
        return get_perms(self.context['request'].user, obj)

    def get_users(self, obj):
        qs = getattr(obj, '{0}userobjectpermission_set'.format(self.Meta.model.__name__.lower()), None)
        if qs:
            return UserObjectPermissionSerializer(qs.all(), many=True).data
        return []

    def get_groups(self, obj):
        qs = getattr(obj, '{0}groupobjectpermission_set'.format(self.Meta.model.__name__.lower()), None)
        if qs:
            return GroupObjectPermissionSerializer(qs.all(), many=True).data
        return []

    def get_public(self, obj):
        publicmodel = 'public{0}'.format(self.Meta.model.__name__.lower())
        if hasattr(obj, publicmodel) and getattr(obj, publicmodel).public:
            return True
        else:
            return False


class LegendSemanticsSerializer(PermissionsModelSerializer):

    id = ModelField(model_field=LegendSemantics._meta.get_field('id'), required=False)

    class Meta:
        model = LegendSemantics
        fields = ('id', 'name', 'description', 'keyword', )


class LegendEntrySerializer(ModelSerializer):

    id = ModelField(model_field=Legend._meta.get_field('id'), required=False)
    semantics = LegendSemanticsSerializer()

    class Meta:
        model = LegendEntry
        fields = ('id', 'semantics', 'expression', 'color', 'code', )


class LegendSerializer(PermissionsModelSerializer):

    entries = LegendEntrySerializer(many=True, source='legendentry_set')
    json = SerializerMethodField()

    class Meta:
        model = Legend
        fields = ('id', 'title', 'description', 'entries', 'json', )
        read_only_fields = ('json', )

    def get_json(self, obj):
        if not obj.json:
            return {}
        return json.loads(obj.json)

    def create_or_update_entries(self, legend, entries):

        for entry_data in entries:

            semantics = entry_data.pop('semantics')

            if 'id' in semantics:
                semantic = get_object_or_404(LegendSemantics, pk=semantics['id'])
            else:
                semantic = LegendSemantics.objects.create(**semantics)

            if 'id' in entry_data:
                entry_id = entry_data.pop('id')
                legend.legendentry_set.filter(id=entry_id).update(**entry_data, semantics_id=semantics['id'])
            else:
                LegendEntry.objects.create(**entry_data, legend=legend, semantics=semantic)

    def create(self, validated_data):
        entries = validated_data.pop('legendentry_set')
        legend = Legend.objects.create(**validated_data)

        self.create_or_update_entries(legend, entries)

        return legend

    def update(self, instance, validated_data):
        if 'title' in validated_data:
            instance.title = validated_data['title']
        if 'description' in validated_data:
            instance.description = validated_data['description']

        entries = validated_data.pop('legendentry_set')
        self.create_or_update_entries(instance, entries)

        instance.save()

        return instance


class RasterLayerParseStatusSerializer(ModelSerializer):

    status_display = SerializerMethodField()

    class Meta:
        model = RasterLayerParseStatus
        exclude = ('id', 'rasterlayer', )

    def get_status_display(self, obj):
        return obj.get_status_display()


class RasterLayerMetadataSerializer(ModelSerializer):

    class Meta:
        model = RasterLayerMetadata
        exclude = ('id', 'rasterlayer', )


class RasterLayerBandMetadataSerializer(ModelSerializer):

    class Meta:
        model = RasterLayerBandMetadata
        exclude = ('id', 'rasterlayer', )


class RasterLayerSerializer(PermissionsModelSerializer):

    metadata = RasterLayerMetadataSerializer(read_only=True)
    bandmetadatas = RasterLayerBandMetadataSerializer(many=True, source='rasterlayerbandmetadata_set', read_only=True)
    parsestatus = RasterLayerParseStatusSerializer(read_only=True)
    reprojected = SerializerMethodField(read_only=True)

    class Meta:
        model = RasterLayer
        fields = (
            'id', 'name', 'description', 'datatype', 'rasterfile', 'source_url', 'nodata', 'srid',
            'max_zoom', 'build_pyramid', 'next_higher', 'store_reprojected', 'legend', 'reprojected', 'metadata', 'parsestatus', 'bandmetadatas',
        )

    def get_reprojected(self, obj):
        if hasattr(obj, 'reprojected') and obj.reprojected.rasterfile:
            return obj.reprojected.rasterfile.url
