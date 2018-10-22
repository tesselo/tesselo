import json

from rest_framework import status

from classify.models import Classifier
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from sentinel.models import Composite


class RasterLegendViewTests(TestCase):

    def setUp(self):

        self.usr = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )
        self.client.login(username='michael', password='bananastand')

    def test_create_predictedlayer(self):
        url = reverse('predictedlayer-list')
        classifier = Classifier.objects.create(name='Classifier')
        composite = Composite.objects.create(name='Composite', min_date='2000-01-01', max_date='2000-03-31')
        response = self.client.post(url, json.dumps({'name': 'Predictedlayer', 'classifier': classifier.id, 'composite': composite.id}), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content.decode())
        self.assertEqual(result['classifier'], classifier.id)
        self.assertEqual(result['composite'], composite.id)
        # The user has permission to see the newly created predicted.
        response = self.client.get(url)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['results'][0]['classifier'], classifier.id)
        # Lucille can not see the layers.
        User.objects.create_user(
            username='lucille',
            email='lucille@bluth.com',
            password='bananastand'
        )
        self.client.login(username='lucille', password='bananastand')
        response = self.client.get(url)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 0)
