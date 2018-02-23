from __future__ import unicode_literals

import json

from guardian.shortcuts import assign_perm
from raster.models import RasterLayer
from raster_aggregation.models import AggregationArea, AggregationLayer, ValueCountResult
from rest_framework import status

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class SentinelViewsTests(TestCase):

    def setUp(self):

        self.usr = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )
        self.client.login(username='michael', password='bananastand')
        self.agglayer = AggregationLayer.objects.create(name='Test Agglayer')
        self.zone = AggregationArea.objects.create(
            aggregationlayer=self.agglayer,
            geom='SRID=4326;MULTIPOLYGON(((-10 68, -10 69, -8 69, -8 68, -10 68)))',
        )
        self.world = {
            'name': 'Sentinel',
            'min_date': '2000-01-01',
            'max_date': '2001-01-01',
            'aggregationlayer': [self.agglayer.id],
        }

    def test_create_composite(self):
        url = reverse('composite-list')

        response = self.client.post(url, json.dumps(self.world), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content.decode())
        self.assertEqual(result['name'], 'Sentinel')
        self.assertEqual(len(result['rasterlayer_lookup']), 13)
        # The user has permission to see the newly created rasterlayers.
        url = reverse('rasterlayer-list')
        response = self.client.get(url)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 13)
        self.assertEqual(result['results'][0]['name'], 'Sentinel - B01.jp2')
        # Lucille can not see the layers.
        User.objects.create_user(
            username='lucille',
            email='lucille@bluth.com',
            password='bananastand'
        )
        self.client.login(username='lucille', password='bananastand')
        url = reverse('rasterlayer-list')
        response = self.client.get(url)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 0)

    def test_create_valuecountresult(self):
        # Create a composite.
        url = reverse('composite-list')
        response = self.client.post(url, json.dumps(self.world), format='json', content_type='application/json')
        agglyr = AggregationLayer.objects.create(name='test')
        assign_perm('view_aggregationlayer', self.usr, agglyr)
        assign_perm('delete_aggregationlayer', self.usr, agglyr)
        agg = AggregationArea.objects.create(
            aggregationlayer=agglyr,
            geom='SRID=4326;MULTIPOLYGON(((0 0, 0 0.00001, 0.00001 0.00001, 0.00001 0, 0 0)))'
        )
        rst = RasterLayer.objects.first()
        url = reverse('valuecountresult-list')
        dat = {
            'formula': 'x',
            'layer_names': {'x': RasterLayer.objects.first().id},
            'zoom': 5,
            'grouping': 'auto',
            'aggregationarea': agg.id,
        }
        response = self.client.post(url, json.dumps(dat), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content.decode())
        self.assertEqual(result['rasterlayers'], [rst.id])
        self.assertEqual(result['formula'], 'x')
        self.assertEqual(result['status'], 'Scheduled')

        # Lucille can not see the result.
        lucille = User.objects.create_user(
            username='lucille',
            email='lucille@bluth.com',
            password='bananastand'
        )
        self.client.login(username='lucille', password='bananastand')
        url = reverse('valuecountresult-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 0)

        # Lucille can not request creating the valuecount result
        # because she does not own the rasterlayers.
        ValueCountResult.objects.all().delete()
        url = reverse('valuecountresult-list')
        dat = {
            'formula': 'x',
            'layer_names': {'x': rst.id},
            'zoom': 5,
            'grouping': 'auto',
            'aggregationarea': agg.id,
        }
        response = self.client.post(url, json.dumps(dat), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Invite lucille to the aggregation area and raster layers, now she can create the value counts.
        self.client.login(username='michael', password='bananastand')
        self.client.get('/api/rasterlayer/{0}/invite/user/view/{1}'.format(rst.id, lucille.id))
        self.client.get('/api/aggregationlayer/{0}/invite/user/view/{1}'.format(agglyr.id, lucille.id))
        self.client.login(username='lucille', password='bananastand')
        response = self.client.post(url, json.dumps(dat), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
