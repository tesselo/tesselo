from __future__ import unicode_literals

import json

from raster.models import LegendSemantics
from rest_framework import status

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase


class RasterLegendViewTests(TestCase):

    def setUp(self):

        self.usr = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )
        self.client.login(username='michael', password='bananastand')

    def test_create_legend(self):

        url = reverse('legend-list')

        data = {
            'title': 'Landcover',
            'description': 'A simple landcover classification.',
            'entries': [
                {'expression': '1', 'color': '#111111', 'semantics': {'name': 'Urban', "description": "Human habitat.", "keyword": "impervious"}, 'code': 'b'},
                {'expression': '2', 'color': '#222222', 'semantics': {'name': 'Forest'}, 'code': 'a'}
            ]
        }
        response = self.client.post(url, json.dumps(data), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content.decode())
        self.assertEqual(result['title'], 'Landcover')
        self.assertEqual(result['description'], 'A simple landcover classification.')
        self.assertEqual(result['json'], [
            {'code': 'a', 'expression': '2', 'color': '#222222', 'name': 'Forest'},
            {'code': 'b', 'expression': '1', 'color': '#111111', 'name': 'Urban'},
        ])

    def test_create_legend_with_semantics_id(self):

        sem = LegendSemantics.objects.create(name="Urban")

        url = reverse('legend-list')

        data = {
            'title': 'Landcover',
            'description': 'A simple landcover classification.',
            'entries': [
                {'expression': '2', 'color': '#222222', 'semantics': {'id': sem.id, 'name': sem.name}, 'code': 'a'}
            ]
        }
        response = self.client.post(url, json.dumps(data), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        result = json.loads(response.content.decode())
        self.assertEqual(result['entries'][0]['semantics']['id'], sem.id)

    def test_invite_user(self):
        gob = User.objects.create(username='Gob', email='gob@bluth.com')

        url = reverse('legend-list')

        data = {
            'title': 'Landcover',
            'description': 'A simple landcover classification.',
            'entries': [
                {'expression': '1', 'color': '#111111', 'semantics': {'name': 'Urban', "description": "Human habitat.", "keyword": "impervious"}, 'code': 'b'},
                {'expression': '2', 'color': '#222222', 'semantics': {'name': 'Forest'}, 'code': 'a'}
            ]
        }
        response = self.client.post(url, json.dumps(data), format='json', content_type='application/json')
        result = json.loads(response.content.decode())

        url = reverse('legend-invite/(?P<invitee-id>[0-9]+)', kwargs={'pk': result['id'], 'invitee_id': gob.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        url = reverse('legend-exclude/(?P<invitee-id>[0-9]+)', kwargs={'pk': result['id'], 'invitee_id': gob.id})
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
