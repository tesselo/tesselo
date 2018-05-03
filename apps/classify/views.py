from rest_framework.filters import SearchFilter

from classify.models import Classifier, PredictedLayer, TrainingSample
from classify.serializers import ClassifierSerializer, PredictedLayerSerializer, TrainingSampleSerializer
from raster_api.views import PermissionsModelViewSet


class TrainingSampleViewSet(PermissionsModelViewSet):

    serializer_class = TrainingSampleSerializer

    _model = 'trainingsample'

    def get_queryset(self):
        return TrainingSample.objects.all().order_by('id')


class ClassifierViewSet(PermissionsModelViewSet):

    serializer_class = ClassifierSerializer
    filter_backends = (SearchFilter, )
    search_fields = ('name', 'algorithm', )

    _model = 'classifier'

    def get_queryset(self):
        return Classifier.objects.all().order_by('id')


class PredictedLayerViewSet(PermissionsModelViewSet):

    serializer_class = PredictedLayerSerializer

    _model = 'predictedlayer'

    def get_queryset(self):
        return PredictedLayer.objects.all().order_by('id')
