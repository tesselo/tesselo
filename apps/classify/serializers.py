from rest_framework.serializers import ModelSerializer, PrimaryKeyRelatedField, SerializerMethodField

from classify.models import Classifier, PredictedLayer, TrainingLayer, TrainingSample


class TrainingLayerSerializer(ModelSerializer):

    trainingsamples = PrimaryKeyRelatedField(many=True, source='trainingsample_set', read_only=True)

    class Meta:
        model = TrainingLayer
        fields = ('id', 'name', 'trainingsamples', )


class TrainingSampleSerializer(ModelSerializer):

    class Meta:
        model = TrainingSample
        fields = (
            'id', 'sentineltile', 'composite', 'geom', 'category', 'value',
            'traininglayer',
        )


class ClassifierSerializer(ModelSerializer):

    traininglayer = PrimaryKeyRelatedField(queryset=TrainingLayer.objects.all(), required=False)

    class Meta:
        model = Classifier
        fields = (
            'id', 'name', 'algorithm', 'traininglayer', 'legend', 'status',
            'log',
        )
        read_only_fields = ('status', 'log', 'legend', )


class PredictedLayerSerializer(ModelSerializer):

    classifier_name = SerializerMethodField()
    source_name = SerializerMethodField()

    class Meta:
        model = PredictedLayer
        fields = (
            'id', 'classifier', 'sentineltile', 'composite', 'rasterlayer',
            'log', 'chunks_count', 'chunks_done', 'classifier_name',
            'source_name', 'status',
        )
        read_only_fields = (
            'rasterlayer', 'log', 'chunks_count', 'chunks_done',
            'classifier_name', 'source_name', 'status',
        )

    def get_classifier_name(self, obj):
        return obj.classifier.name

    def get_source_name(self, obj):
        if obj.composite:
            return obj.composite.name
        else:
            return obj.sentineltile.collected.date()
