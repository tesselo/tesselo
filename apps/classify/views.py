from classify.models import Classifier, TrainingSample
from classify.serializers import ClassifierSerializer, TrainingSampleSerializer
from raster_api.views import PermissionsModelViewSet


class TrainingSampleViewSet(PermissionsModelViewSet):

    serializer_class = TrainingSampleSerializer

    _model = 'trainingsample'

    def get_queryset(self):
        return TrainingSample.objects.all().order_by('id')


class ClassifierViewSet(PermissionsModelViewSet):

    serializer_class = ClassifierSerializer

    _model = 'classifier'

    def get_queryset(self):
        return Classifier.objects.all().order_by('id')
