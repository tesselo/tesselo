import numpy
from rest_framework.decorators import detail_route
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from classify.models import Classifier, PredictedLayer, TrainingLayer, TrainingSample
from classify.serializers import (
    ClassifierSerializer, PredictedLayerSerializer, TrainingLayerSerializer, TrainingSampleSerializer
)
from classify.tasks import CLASSIFY_BAND_NAMES, get_training_matrix
from django.http import HttpResponse
from raster_api.permissions import ChangePermissionObjectPermission
from raster_api.views import PermissionsModelViewSet
from sentinel import ecs


class TrainingLayerViewSet(PermissionsModelViewSet):

    serializer_class = TrainingLayerSerializer
    queryset = TrainingLayer.objects.all().order_by('id')
    filter_backends = (SearchFilter, )
    search_fields = ('name', )

    _model = 'traininglayer'

    @detail_route(methods=['get'], permission_classes=[IsAuthenticated, ChangePermissionObjectPermission])
    def trainingdata(self, request, pk):
        """
        Get the training data from this training layer.
        """
        # Get training data.
        categories, X, Y = get_training_matrix(self.get_object())
        # Append class values to matrix.
        data = numpy.append(Y.reshape((len(Y), 1)), X, 1).astype('uint16')
        # Append class names to matrix.
        names = numpy.chararray(Y.shape, itemsize=max(len(key) for key in categories.keys()))
        for key, val in categories.items():
            names[Y == val] = key
        data = numpy.append(names.reshape((len(names), 1)), data, 1)
        # Append header to matrix.
        header = numpy.array(['ClassName', 'ClassDigitalNumber'] + [band.split('.jp2')[0] for band in CLASSIFY_BAND_NAMES])
        data = numpy.append(header.reshape((1, len(header))), data, 0)

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="trainingdata.csv"'
        numpy.savetxt(response, data, delimiter=',', fmt='%s')

        return response


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

    @detail_route(methods=['post'], permission_classes=[IsAuthenticated, ChangePermissionObjectPermission])
    def train(self, request, pk):
        """
        Train this classifier.
        """
        classifier = self.get_object()
        classifier.status = classifier.PENDING
        classifier.save()
        ecs.train_sentinel_classifier(classifier.id)
        return Response({'success': 'Triggered Classifier Training {}'.format(classifier.id)})


class PredictedLayerViewSet(PermissionsModelViewSet):

    serializer_class = PredictedLayerSerializer

    filter_fields = ('classifier', 'sentineltile', )

    _model = 'predictedlayer'

    def get_queryset(self):
        return PredictedLayer.objects.all().order_by('id')

    @detail_route(methods=['post'], permission_classes=[IsAuthenticated, ChangePermissionObjectPermission])
    def predict(self, request, pk):
        """
        Predict this layer.
        """
        pred = self.get_object()
        pred.write('Scheduled layer prediction', pred.PENDING)
        ecs.predict_sentinel_layer(pred.id)
        return Response({'success': 'Triggered Layer Prediction {}'.format(pred.id)})
