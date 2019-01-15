import json

from rest_framework.serializers import CharField, ModelSerializer, PrimaryKeyRelatedField, SerializerMethodField

from classify.models import (
    Classifier, ClassifierAccuracy, PredictedLayer, PredictedLayerChunk, TrainingLayer, TrainingSample
)


class TrainingLayerSerializer(ModelSerializer):

    trainingsamples = PrimaryKeyRelatedField(many=True, source='trainingsample_set', read_only=True)

    class Meta:
        model = TrainingLayer
        fields = ('id', 'name', 'trainingsamples', 'legend', )


class TrainingSampleSerializer(ModelSerializer):

    class Meta:
        model = TrainingSample
        fields = (
            'id', 'sentineltile', 'composite', 'geom', 'category', 'value',
            'traininglayer',
        )


class ClassifierAccuracySerializer(ModelSerializer):

    class Meta:
        model = ClassifierAccuracy
        fields = ('accuracy_score', 'accuracy_matrix', 'cohen_kappa')


class ClassifierSerializer(ModelSerializer):

    traininglayer = PrimaryKeyRelatedField(queryset=TrainingLayer.objects.all(), required=False)
    classifieraccuracy = ClassifierAccuracySerializer(read_only=True)
    legend = CharField(source='traininglayer.legend', read_only=True)

    class Meta:
        model = Classifier
        fields = (
            'id', 'name', 'algorithm', 'traininglayer', 'legend', 'status',
            'log', 'classifieraccuracy', 'splitfraction',
        )
        read_only_fields = ('status', 'log', 'legend', 'classifieraccuracy', )


class PredictedLayerSerializer(ModelSerializer):

    classifier_name = SerializerMethodField()
    classifier_type = SerializerMethodField()
    source_name = SerializerMethodField()
    chunks_count = SerializerMethodField()
    chunks_done = SerializerMethodField()
    aggregationlayer_name = SerializerMethodField()
    legend = SerializerMethodField()

    class Meta:
        model = PredictedLayer
        fields = (
            'id', 'classifier', 'sentineltile', 'composite', 'rasterlayer',
            'log', 'chunks_count', 'chunks_done', 'classifier_name',
            'source_name', 'status', 'aggregationlayer', 'classifier_type',
            'aggregationlayer_name', 'legend',
        )
        read_only_fields = (
            'rasterlayer', 'log', 'chunks_count', 'chunks_done',
            'classifier_name', 'source_name', 'status', 'legend',
        )

    def get_classifier_name(self, obj):
        return obj.classifier.name

    def get_classifier_type(self, obj):
        return obj.classifier.get_algorithm_display()

    def get_source_name(self, obj):
        if obj.composite:
            return obj.composite.name
        else:
            return obj.sentineltile.collected.date()

    def get_aggregationlayer_name(self, obj):
        if obj.aggregationlayer:
            return obj.aggregationlayer.name
        else:
            return ''

    def get_chunks_count(self, obj):
        return obj.predictedlayerchunk_set.count()

    def get_chunks_done(self, obj):
        return obj.predictedlayerchunk_set.filter(status=PredictedLayerChunk.FINISHED).count()

    def get_legend(self, obj):
        if obj.rasterlayer.legend:
            return json.loads(obj.rasterlayer.legend.json)
        else:
            return {}
