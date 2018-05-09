
import mock
from raster_aggregation.models import AggregationArea, AggregationLayer
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from classify.models import Classifier, PredictedLayer
from django.contrib.auth.models import User
from django.contrib.gis.gdal import OGRGeometry
from django.test import TestCase, override_settings
from django.urls import reverse
from sentinel.models import Composite, CompositeBuild


@mock.patch('sentinel.ecs.composite_build_callback', lambda *args, **kwargs: None)
@mock.patch('sentinel.ecs.process_compositetile', lambda *args, **kwargs: None)
@mock.patch('sentinel.ecs.train_sentinel_classifier', lambda *args, **kwargs: None)
@mock.patch('sentinel.ecs.predict_sentinel_layer', lambda *args, **kwargs: None)
@override_settings(CELERY_TASK_ALWAYS_EAGER=True, LOCAL=True)
class SentinelApiTriggers(TestCase):

    def setUp(self):
        bbox = [11833687.0, -469452.0, 11859687.0, -441452.0]
        bbox = OGRGeometry.from_bbox(bbox)
        bbox.srid = 3857
        self.agglayer = AggregationLayer.objects.create(name='Test Agg Layer')
        self.zone = AggregationArea.objects.create(
            name='Test Agg Area',
            aggregationlayer=self.agglayer,
            geom='SRID=3857;MULTIPOLYGON((( 11833687.0 -469452.0, 11859687.0 -469452.0, 11859687.0 -441452.0, 11833687.0 -441452.0, 11833687.0 -469452.0)))'
        )

        self.composite = Composite.objects.create(name='The World', min_date='2000-01-01', max_date='2100-01-01')
        self.build = CompositeBuild.objects.create(composite=self.composite, aggregationlayer=self.agglayer)
        self.michael = User.objects.create_superuser(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )
        # Authenticate user.
        self.client.login(username='michael', password='bananastand')

    def test_composite_build_trigger(self):
        # Get url.
        url = reverse('compositebuild-build', kwargs={'pk': self.build.id})
        # Request build.
        response = self.client.post(url)
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data, {'success': 'Triggered Composite Build {}'.format(self.build.id)})
        # Request build on build that is currently running.
        self.build.status = CompositeBuild.BUILDING_TILES
        self.build.save()
        response = self.client.post(url)
        self.assertEqual(
            response.data,
            {'error': 'Composite Build is already in process. Wait until build finishes before triggering a new build.'},
        )
        self.assertEqual(response.status_code, HTTP_400_BAD_REQUEST)

    def test_composite_tile_build_trigger(self):
        self.build.set_compositetiles()
        ctile = self.build.composite.compositetile_set.first()
        # Get url.
        url = reverse('compositetile-build', kwargs={'pk': ctile.id})
        # Request tile build.
        response = self.client.post(url)
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data, {'success': 'Triggered Composite Tile Build {}'.format(ctile.id)})

    def test_classifier_training_trigger(self):
        clf = Classifier.objects.create(name='Test Classifier', algorithm=Classifier.SVM)
        # Get url.
        url = reverse('classifier-train', kwargs={'pk': clf.id})
        # Request tile build.
        response = self.client.post(url)
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data, {'success': 'Triggered Classifier Training {}'.format(clf.id)})

    def test_layer_prediction_trigger(self):
        clf = Classifier.objects.create(name='Test Classifier', algorithm=Classifier.SVM)
        pred = PredictedLayer.objects.create(classifier=clf)
        # Get url.
        url = reverse('predictedlayer-predict', kwargs={'pk': pred.id})
        # Request tile build.
        response = self.client.post(url)
        self.assertEqual(response.status_code, HTTP_200_OK)
        self.assertEqual(response.data, {'success': 'Triggered Layer Prediction {}'.format(pred.id)})
