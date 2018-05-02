from rest_framework.serializers import ModelSerializer

from classify.models import Classifier, TrainingSample


class TrainingSampleSerializer(ModelSerializer):

    class Meta:
        model = TrainingSample
        fields = ('id', 'sentineltile', 'composite', 'geom', 'category', 'value')


class ClassifierSerializer(ModelSerializer):

    class Meta:
        model = Classifier
        fields = ('id', 'name', 'algorithm', 'trainingsamples', 'legend')
