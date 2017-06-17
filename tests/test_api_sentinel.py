from __future__ import unicode_literals

import json

from rest_framework import status

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase
from sentinel.models import WorldLayerGroup, ZoneOfInterest


class SentinelViewsTests(TestCase):

    def setUp(self):

        self.usr = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )
        self.client.login(username='michael', password='bananastand')
        self.zone = ZoneOfInterest.objects.create(
            name='Zone',
            geom='SRID=4326;POLYGON ((-10 68, -10 69, -8 69, -8 68, -10 68))',
            active=False,
        )
        self.world = {
            'name': 'Sentinel',
            'all_zones': False,
            'min_date': '2000-01-01',
            'max_date': '2001-01-01',
            'zonesofinterest': [self.zone.id],
        }

    def test_create_worldlayergroup(self):
        url = reverse('worldlayergroup-list')

        response = self.client.post(url, json.dumps(self.world), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content.decode())
        self.assertEqual(result['name'], 'Sentinel')
        self.assertEqual(len(result['kahunas']), 13)
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

    def test_create_zone_of_interest(self):
        url = reverse('zoneofinterest-list')
        data = {
            'name': 'Zone api',
            'geom': self.zone.geom.ewkt,
        }
        response = self.client.post(url, json.dumps(data), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content.decode())
        self.assertEqual(result['name'], 'Zone api')
        self.assertEqual(result['geom'], self.zone.geom.ewkt)

        # Test filters.
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 1)

        response = self.client.get(url + '?active=false')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 0)

        response = self.client.get(url + '?active=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 1)

        self.world.pop('zonesofinterest')
        world = WorldLayerGroup.objects.create(**self.world)
        world.zonesofinterest.add(result['results'][0]['id'])
        response = self.client.get(url + '?worldlayergroup=' + str(world.id))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 1)

        response = self.client.get(url + '?worldlayergroup=23')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 0)