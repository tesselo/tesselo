import json
from django.shortcuts import get_object_or_404
from rest_framework.serializers import ModelSerializer, SerializerMethodField, CharField, BooleanField
from raster.models import Legend, LegendEntry, LegendSemantics, RasterLayer, RasterLayerMetadata, RasterLayerParseStatus, RasterLayerBandMetadata


class LegendSemanticsSerializer(ModelSerializer):

    class Meta:
        model = LegendSemantics
        fields = ('id', 'name', 'description', 'keyword', )


class LegendEntrySerializer(ModelSerializer):

    semantics = LegendSemanticsSerializer()
    code = SerializerMethodField()

    class Meta:
        model = LegendEntry
        fields = ('id', 'semantics', 'expression', 'color', 'code', )

    def get_code(self, obj):
        entry_order = obj.legendentryorder_set.first()
        if entry_order:
            return entry_order.code


class LegendSerializer(ModelSerializer):

    entries = LegendEntrySerializer(many=True)

    json = SerializerMethodField()

    class Meta:
        model = Legend
        fields = ('id', 'title', 'description', 'entries', 'json', )
        read_only_fields = ('json', )

    def get_json(self, obj):
        if not obj.json:
            return {}
        return json.loads(obj.json)


    def create(self, validated_data):
        entries = validated_data.pop('entries')
        legend = Legend.objects.create(**validated_data)
        for entry in entries:

            code = entry.pop('code', '')
            semantics = entry.pop('semantics')

            if 'id' in semantics:
                semantic = get_object_or_404(LegendSemantics, pk=semantics['id'])
            else:
                semantic = LegendSemantics.objects.create(**semantics)

            LegendEntry.objects.create(**entry, semantics=semantic)

        return legend


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


class RasterLayerSerializer(ModelSerializer):

    metadata = RasterLayerMetadataSerializer(read_only=True)
    bandmetadatas = RasterLayerBandMetadataSerializer(many=True, source='rasterlayerbandmetadata_set', read_only=True)
    parsestatus = RasterLayerParseStatusSerializer(read_only=True)
    reprojected = SerializerMethodField(read_only=True)
    public = SerializerMethodField(read_only=True)

    class Meta:
        model = RasterLayer
        fields = (
            'id', 'name', 'description', 'datatype', 'rasterfile', 'source_url', 'nodata', 'srid',
            'max_zoom', 'build_pyramid', 'next_higher', 'store_reprojected', 'legend', 'reprojected', 'metadata', 'parsestatus', 'bandmetadatas', 'public',
        )

    def get_reprojected(self, obj):
        if hasattr(obj ,'reprojected') and obj.reprojected.rasterfile:
            return obj.reprojected.rasterfile.url

    def get_public(self, obj):
        if hasattr(obj, 'publicrasterlayer') and obj.publicrasterlayer.public:
            return True
        else:
            return False
