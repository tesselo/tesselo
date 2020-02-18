import numpy
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from classify.filters import PredictedLayerFilter
from classify.models import Classifier, PredictedLayer, TrainingLayer, TrainingSample
from classify.serializers import (
    ClassifierSerializer, PredictedLayerSerializer, TrainingLayerSerializer, TrainingSampleSerializer
)
from django.http import HttpResponse
from jobs import ecs
from raster_api.permissions import ChangePermissionObjectPermission, IsReadOnly
from raster_api.views import PermissionsModelViewSet


class TrainingLayerViewSet(PermissionsModelViewSet):

    serializer_class = TrainingLayerSerializer
    queryset = TrainingLayer.objects.all().order_by('id')
    filter_backends = (SearchFilter, )
    search_fields = ('name', )

    _model = 'traininglayer'


class TrainingSampleViewSet(PermissionsModelViewSet):

    serializer_class = TrainingSampleSerializer

    _model = 'trainingsample'

    queryset = TrainingSample.objects.all().order_by('id')


class ClassifierViewSet(PermissionsModelViewSet):

    serializer_class = ClassifierSerializer
    filter_backends = (SearchFilter, )
    search_fields = ('name', 'algorithm', )

    _model = 'classifier'

    queryset = Classifier.objects.all().order_by('id')

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsReadOnly, ChangePermissionObjectPermission])
    def train(self, request, pk):
        """
        Train this classifier.
        """
        classifier = self.get_object()
        classifier.status = classifier.PENDING
        classifier.save()
        ecs.train_sentinel_classifier(classifier.id)
        return Response({'success': 'Triggered Classifier Training {}'.format(classifier.id)})

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsReadOnly, ChangePermissionObjectPermission])
    def report(self, request, pk):
        """
        Accuracy assessment report.
        """
        classifier = self.get_object()

        if not hasattr(classifier, 'classifieraccuracy'):
            return HttpResponse('')
        else:
            acc = classifier.classifieraccuracy

        # Get row and col names
        names = [acc.classifier.traininglayer.legend[dat] for dat in sorted(acc.classifier.traininglayer.legend)]

        # Add names to accuracy matrix.
        data = numpy.array(acc.accuracy_matrix).astype('str')
        data = numpy.vstack([names, data])

        names = [''] + names
        data = numpy.hstack([numpy.array(names).reshape((len(names), 1)), data])

        # Add additional header rows to accuracy matrix.
        head = [''] * len(names)
        head[1] = 'Predicted class'
        data = numpy.vstack([head, data])

        head = [''] * len(names)
        head[2] = 'Actual class'
        head.append('')
        data = numpy.hstack([numpy.array(head).reshape((len(head), 1)), data])

        # Add producers and consumers accuracy to matrix.
        producers = ['', 'Consumers Accuracy'] + (numpy.diag(acc.accuracy_matrix) / numpy.sum(acc.accuracy_matrix, axis=0)).astype('str').tolist()
        consumers = ['', 'Producers Accuracy'] + (numpy.diag(acc.accuracy_matrix) / numpy.sum(acc.accuracy_matrix, axis=1)).astype('str').tolist()
        consumers.append('')

        data = numpy.vstack([data, producers])
        data = numpy.hstack([data, numpy.array(consumers).reshape((len(consumers), 1))])

        # Addd overarching statistics.
        overall = [''] * len(consumers)
        overall[0] = 'Overall Accuracy Score'
        overall[1] = str(acc.accuracy_score)
        data = numpy.vstack([data, overall])

        kappa = [''] * len(consumers)
        kappa[0] = 'Cohen Kappa Score'
        kappa[1] = str(acc.cohen_kappa)
        data = numpy.vstack([data, kappa])

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="accuracy_classifier_{}.csv"'.format(classifier.id)
        numpy.savetxt(response, data, delimiter=',', fmt='%s')

        return response


class PredictedLayerViewSet(PermissionsModelViewSet):

    serializer_class = PredictedLayerSerializer

    filter_class = PredictedLayerFilter

    _model = 'predictedlayer'

    queryset = PredictedLayer.objects.all().select_related(
        'rasterlayer', 'rasterlayer__legend', 'classifier', 'aggregationlayer'
    ).prefetch_related(
        'predictedlayerchunk_set'
    ).order_by('id')

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated, IsReadOnly, ChangePermissionObjectPermission])
    def predict(self, request, pk):
        """
        Predict this layer.
        """
        pred = self.get_object()
        pred.write('Scheduled layer prediction', pred.PENDING)
        ecs.predict_sentinel_layer(pred.id)
        return Response({'success': 'Triggered Layer Prediction {}'.format(pred.id)})
