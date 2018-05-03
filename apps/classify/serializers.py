from rest_framework.serializers import ModelSerializer, PrimaryKeyRelatedField

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

    class Meta:
        model = PredictedLayer
        fields = ('classifier', 'sentineltile', 'composite', 'rasterlayer', 'log', 'created', )
        read_only_fields = ('rasterlayer', 'created', 'log', )
