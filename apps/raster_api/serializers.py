import json

from guardian.shortcuts import assign_perm, get_perms
from raster.models import (
    Legend, LegendEntry, LegendSemantics, RasterLayer, RasterLayerBandMetadata, RasterLayerMetadata,
    RasterLayerParseStatus
)
from raster.tiles.const import WEB_MERCATOR_SRID
from raster_aggregation.models import AggregationLayer
from raster_aggregation.serializers import AggregationLayerSerializer as AggregationLayerSerializerOriginal
from raster_aggregation.serializers import ValueCountResultSerializer as ValueCountResultSerializerOriginal
from rest_framework.serializers import (
    CharField, FloatField, IntegerField, ModelField, ModelSerializer, Serializer, SerializerMethodField
)

from django.contrib.auth.models import Group, User
from django.contrib.gis.db.models import Extent
from django.contrib.gis.geos import Polygon
from django.shortcuts import get_object_or_404
from raster_api.models import ReadOnlyToken
from sentinel.models import Composite, SentinelTileAggregationLayer


class ReadOnlyTokenSerializer(ModelSerializer):

    class Meta:
        model = ReadOnlyToken
        fields = ('key', 'user', )
        read_only_fields = ('user', 'key', )

    def create(self, validated_data):
        validated_data.update({'user': self.context['request'].user})
        return super(ReadOnlyTokenSerializer, self).create(validated_data)


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

    _public = None

    def get_public(self, obj):

        if self._public is None:
            publicmodel = 'public{0}'.format(self.Meta.model.__name__.lower())
            if hasattr(obj, publicmodel) and getattr(obj, publicmodel).public:
                self._public = True
            else:
                self._public = False

        return self._public


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

    entries = LegendEntrySerializer(many=True, source='legendentry_set', required=False)
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
                # Ensure that the semantic is not private for puplic legends.
                if hasattr(semantic, 'publiclegendsemantics') and not semantic.publiclegendsemantics.public and self.get_public(legend):
                    continue
            else:
                semantic = LegendSemantics.objects.create(**semantics)
                # Make new semantics public if legend is public.
                if legend.publiclegend.public:
                    semantic.pucliclegendsemantics.public = True
                    semantic.pucliclegendsemantics.save()
                # Assign permissions to new semantics.
                assign_perm('view_legendsemantics', self.context['request'].user, semantic)
                assign_perm('change_legendsemantics', self.context['request'].user, semantic)
                assign_perm('delete_legendsemantics', self.context['request'].user, semantic)
            if 'id' in entry_data:
                entry_id = entry_data.pop('id')
                legend.legendentry_set.filter(pk=entry_id).update(semantics_id=semantics['id'], **entry_data)
            else:
                LegendEntry.objects.create(legend=legend, semantics=semantic, **entry_data)

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

        entries = validated_data.pop('legendentry_set', None)
        if entries:
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

    def check_legend_public_status(self, layer):
        """
        Unset legend if layer is public but legend is not.
        """
        if layer.publicrasterlayer.public and layer.legend and not layer.legend.publiclegend.public:
            layer.legend = None
            layer.save()
        return layer

    def create(self, validated_data):
        layer = super(RasterLayerSerializer, self).create(validated_data)
        return self.check_legend_public_status(layer)

    def update(self, instance, validated_data):
        instance = super(RasterLayerSerializer, self).update(instance, validated_data)
        return self.check_legend_public_status(instance)


class CompositeSerializer(PermissionsModelSerializer):

    start_week = SerializerMethodField()

    class Meta:
        model = Composite
        fields = (
            'id', 'name', 'rasterlayer_lookup', 'compositeband_set', 'min_date',
            'max_date', 'interval', 'official', 'max_cloudy_pixel_percentage',
            'active', 'start_week', 'interval', 'sentineltiles',
        )
        read_only_fields = (
            'rasterlayer_lookup', 'compositeband_set', 'official', 'interval',
            'sentineltiles',
        )

    def get_start_week(self, obj):
        return obj.min_date.isocalendar()[1]


class SentinelTileAggregationLayerSerializer(PermissionsModelSerializer):

    sentineltile_id = IntegerField(source='sentineltile.id')
    rasterlayer_lookup = SerializerMethodField()
    name = CharField(source='sentineltile.prefix')
    date = SerializerMethodField()
    mgrs = CharField(source='sentineltile.mgrstile.code')
    cloudy_pixel_percentage = CharField(source='sentineltile.cloudy_pixel_percentage')
    data_coverage_percentage = CharField(source='sentineltile.data_coverage_percentage')
    angle_azimuth = CharField(source='sentineltile.angle_azimuth')
    angle_altitude = CharField(source='sentineltile.angle_altitude')
    level = CharField(source='sentineltile.level')
    status = CharField(source='sentineltile.status')

    class Meta:
        model = SentinelTileAggregationLayer
        fields = (
            'id', 'name', 'rasterlayer_lookup', 'active', 'date', 'mgrs',
            'sentineltile_id', 'cloudy_pixel_percentage', 'data_coverage_percentage',
            'angle_azimuth', 'angle_altitude', 'level', 'status',
        )

    def get_rasterlayer_lookup(self, obj):
        return {band.band: band.layer_id for band in obj.sentineltile.sentineltileband_set.all()}

    def get_date(self, obj):
        return obj.sentineltile.collected.date()


class AggregationLayerSerializer(AggregationLayerSerializerOriginal):

    extent = SerializerMethodField()
    shapefile = CharField(write_only=False, required=False)
    name_column = CharField(write_only=False, required=False)
    simplification_tolerance = FloatField(write_only=True, required=False)

    class Meta:
        model = AggregationLayer
        fields = (
            'id', 'name', 'description', 'min_zoom_level', 'max_zoom_level',
            'nr_of_areas', 'simplification_tolerance', 'aggregationareas',
            'extent', 'shapefile', 'name_column', 'simplification_tolerance',
            'parse_log',
        )
        read_only_fields = ('nr_of_areas', )

    def get_extent(self, obj):
        extent = obj.aggregationarea_set.aggregate(Extent('geom'))['geom__extent']
        # If this aggregation area does not have any geometries, return global
        # view as placeholder.
        if not extent:
            return -180, -90, 180, 90
        extent = Polygon.from_bbox(extent)
        extent.srid = WEB_MERCATOR_SRID
        extent.transform(4326)
        return extent.extent


class ValueCountResultSerializer(ValueCountResultSerializerOriginal):

    name = CharField(source='aggregationarea.name', read_only=True)

    class Meta(ValueCountResultSerializerOriginal.Meta):
        fields = ValueCountResultSerializerOriginal.Meta.fields + ('name', )
