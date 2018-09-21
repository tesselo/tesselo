import numpy
from rest_framework.decorators import detail_route
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from classify.models import Classifier, PredictedLayer, TrainingLayer, TrainingSample
from classify.serializers import (
    ClassifierSerializer, PredictedLayerSerializer, TrainingLayerSerializer, TrainingSampleSerializer
)
from classify.tasks import CLASSIFY_BAND_NAMES, populate_training_matrix
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
        obj = self.get_object()
        # Get training data.
        X, Y, PID = populate_training_matrix(obj)
        # Append class values to matrix.
        data = numpy.append(Y.reshape((len(Y), 1)), X, 1).astype('int64')
        # Append class names to matrix.
        names = numpy.chararray(Y.shape, itemsize=max(len(category_name) for category_name in obj.legend.values()))
        for category_dn, category_name in obj.legend.items():
            names[Y == int(category_dn)] = category_name
        data = numpy.append(names.reshape((len(names), 1)), data, 1)
        # Apend pixel ids to matrix.
        data = numpy.append(PID.reshape((len(PID), 1)).astype('int64'), data, 1)
        # Append header to matrix.
        header = numpy.array(['PixelId', 'ClassName', 'ClassDigitalNumber'] + [band.split('.jp2')[0] for band in CLASSIFY_BAND_NAMES])
        data = numpy.append(header.reshape((1, len(header))), data, 0)
        # Return data as csv.
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

    @detail_route(methods=['get'], permission_classes=[IsAuthenticated, ChangePermissionObjectPermission])
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
