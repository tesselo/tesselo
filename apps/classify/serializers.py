from rest_framework.serializers import ModelSerializer, PrimaryKeyRelatedField, SerializerMethodField

from classify.models import Classifier, PredictedLayer, TrainingSample


class TrainingSampleSerializer(ModelSerializer):

    class Meta:
        model = TrainingSample
        fields = ('id', 'sentineltile', 'composite', 'geom', 'category', 'value')


class ClassifierSerializer(ModelSerializer):

    trainingsamples = PrimaryKeyRelatedField(queryset=TrainingSample.objects.all(), many=True, required=False)

    class Meta:
        model = Classifier
        fields = ('id', 'name', 'algorithm', 'trainingsamples', 'legend')


class PredictedLayerSerializer(ModelSerializer):

    classifier_name = SerializerMethodField()
    source_name = SerializerMethodField()

    class Meta:
        model = PredictedLayer
        fields = (
            'id', 'classifier', 'sentineltile', 'composite', 'rasterlayer',
            'log', 'chunks_count', 'chunks_done', 'classifier_name',
            'source_name',
        )
        read_only_fields = (
            'rasterlayer', 'log', 'chunks_count', 'chunks_done',
            'classifier_name', 'source_name',
        )

    def get_classifier_name(self, obj):
        return obj.classifier.name

    def get_source_name(self, obj):
        if obj.composite:
            return obj.composite.name
        else:
            return obj.sentineltile.collected.date()
