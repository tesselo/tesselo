from classify.models import Classifier, TrainingSample
from classify.serializers import ClassifierSerializer, TrainingSampleSerializer
from raster_api.views import PermissionsModelViewSet
from rest_framework.filters import SearchFilter


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
