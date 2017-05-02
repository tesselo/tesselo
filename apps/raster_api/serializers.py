import json
from django.shortcuts import get_object_or_404
from rest_framework.serializers import ModelSerializer, SerializerMethodField, CharField
from raster.models import Legend, LegendEntry, LegendSemantics, LegendEntryOrder, RasterLayer, RasterLayerMetadata, RasterLayerParseStatus, RasterLayerBandMetadata


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
        return obj.legendentryorder_set.first().code


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
            print(semantics)
            if 'id' in semantics:
                semantic = get_object_or_404(LegendSemantics, pk=semantics['id'])
            else:
                semantic = LegendSemantics.objects.create(**semantics)

            entry = LegendEntry.objects.create(**entry, semantics=semantic)

            LegendEntryOrder.objects.create(legendentry=entry, legend=legend, code=code)

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

    metadata = RasterLayerMetadataSerializer()
    bandmetadatas = RasterLayerBandMetadataSerializer(many=True, source='rasterlayerbandmetadata_set')
    parsestatus = RasterLayerParseStatusSerializer()
    reprojected = SerializerMethodField()

    class Meta:
        model = RasterLayer
        fields = (
            'id', 'name', 'description', 'datatype', 'rasterfile', 'source_url', 'nodata', 'srid',
            'max_zoom', 'build_pyramid', 'next_higher', 'store_reprojected', 'legend', 'reprojected', 'metadata', 'parsestatus', 'bandmetadatas'
        )
        read_only_fields = ('reprojected', 'metadata',)

    def get_reprojected(self, obj):
        if obj.reprojected:
            return obj.reprojected.rasterfile.url
