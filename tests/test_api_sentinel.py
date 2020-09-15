import copy
import json
from urllib.parse import urlencode

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from guardian.shortcuts import assign_perm
from raster.models import RasterLayer
from raster_aggregation.models import AggregationArea, AggregationLayer, ValueCountResult
from rest_framework import status


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
        # All 13 S2 bands plus 2 S1 bands.
        self.assertEqual(len(result['rasterlayer_lookup']), 13 + 1 + 2)
        # The user has permission to see the newly created rasterlayers.
        url = reverse('rasterlayer-list')
        response = self.client.get(url)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 13 + 1 + 2)
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
        # Create necessary objects for valuecount.
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
        rst.publicrasterlayer.public = False
        rst.publicrasterlayer.save()
        # Create value count object.
        url = reverse('valuecountresult-list')
        dat = {
            'formula': 'x',
            'layer_names': {'x': rst.id},
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
        valuecount_id = result['id']

        # Construct get url with query paramerers.
        dat_get = copy.deepcopy(dat)
        dat_get['layer_names'] = json.dumps(dat_get['layer_names'])
        dat_get = urlencode(dat_get)
        url_get = url + '?' + dat_get

        # Try to get object.
        response = self.client.get(url_get)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['count'], 1)
        self.assertEqual(response.json()['results'][0]['id'], valuecount_id)
        # Try with pk.
        response = self.client.get(url + '/{}'.format(valuecount_id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()['id'], valuecount_id)

        # Lucille can not see the result.
        lucille = User.objects.create_user(
            username='lucille',
            email='lucille@bluth.com',
            password='bananastand'
        )
        self.client.login(username='lucille', password='bananastand')

        # Try to get object.
        response = self.client.get(url_get)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Try with pk.
        response = self.client.get(url + '/{}'.format(valuecount_id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Try deleting.
        response = self.client.delete(url + '/{}'.format(valuecount_id))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Michael can delete object.
        self.client.login(username='michael', password='bananastand')
        response = self.client.delete(url + '/{}'.format(valuecount_id))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(ValueCountResult.objects.all().count(), 0)
        response = self.client.delete(url + '/{}'.format(valuecount_id))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Lucille can not request creating the valuecount result
        # because she does not own the rasterlayers.
        self.client.login(username='lucille', password='bananastand')
        response = self.client.post(url, json.dumps(dat), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Invite lucille to the aggregation area and raster layers, now she can create the value counts.
        self.client.login(username='michael', password='bananastand')
        self.client.get('/rasterlayer/{0}/invite/user/view/{1}'.format(rst.id, lucille.id))
        self.client.get('/aggregationlayer/{0}/invite/user/view/{1}'.format(agglyr.id, lucille.id))
        self.client.login(username='lucille', password='bananastand')
        response = self.client.post(url, json.dumps(dat), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
