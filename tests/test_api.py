from __future__ import unicode_literals

import json

from raster.models import Legend, LegendSemantics
from rest_framework import status

from django.contrib.auth.models import User
from django.core.urlresolvers import reverse
from django.test import TestCase
from guardian.shortcuts import assign_perm


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

    def test_update_legend(self):
        leg = Legend.objects.create(title="Landcover")
        assign_perm('view_legend', self.usr, leg)
        assign_perm('change_legend', self.usr, leg)

        url = reverse('legend-detail', kwargs={'pk': leg.id})

        # Create new expressions.
        data = {
            'title': 'Landcover Updated',
            'description': 'A simple landcover classification.',
            'entries': [
                {'expression': '1', 'color': '#111111', 'semantics': {'name': 'Urban', "description": "Human habitat.", "keyword": "impervious"}, 'code': 'b'},
                {'expression': '2', 'color': '#222222', 'semantics': {'name': 'Forest'}, 'code': 'a'},
            ]
        }
        response = self.client.put(url, json.dumps(data), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content.decode())
        self.assertEqual(result['title'], 'Landcover Updated')
        self.assertEqual(result['description'], 'A simple landcover classification.')
        self.assertEqual(result['json'], [
            {'code': 'a', 'expression': '2', 'color': '#222222', 'name': 'Forest'},
            {'code': 'b', 'expression': '1', 'color': '#111111', 'name': 'Urban'},
        ])

        # Update expressions.
        data = {'entries': result['entries']}
        data['entries'][0]['color'] = '#333333'
        data['entries'][0]['expression'] = '3'
        data['entries'][1]['color'] = '#444444'
        data['entries'][1]['expression'] = '4'
        response = self.client.patch(url, json.dumps(data), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content.decode())
        self.assertEqual(result['title'], 'Landcover Updated')
        self.assertEqual(result['description'], 'A simple landcover classification.')
        self.assertEqual(result['json'], [
            {'code': 'a', 'expression': '3', 'color': '#333333', 'name': 'Forest'},
            {'code': 'b', 'expression': '4', 'color': '#444444', 'name': 'Urban'},
        ])

        # Add expressions.
        data = {'entries': [{'expression': '5', 'color': '#555555', 'semantics': {'name': 'Water'}, 'code': '0'}]}
        response = self.client.patch(url, json.dumps(data), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content.decode())
        self.assertEqual(result['json'], [
            {'code': '0', 'expression': '5', 'color': '#555555', 'name': 'Water'},
            {'code': 'a', 'expression': '3', 'color': '#333333', 'name': 'Forest'},
            {'code': 'b', 'expression': '4', 'color': '#444444', 'name': 'Urban'},
        ])

    def test_private_public_semantics_conflict(self):
        leg = Legend.objects.create(title="Landcover")
        assign_perm('view_legend', self.usr, leg)
        assign_perm('change_legend', self.usr, leg)
        leg.publiclegend.public = True
        leg.publiclegend.save()

        url = reverse('legend-detail', kwargs={'pk': leg.id})

        sem = LegendSemantics.objects.create(name='Private semantics')

        entires_count = leg.legendentry_set.count()

        data = {'entries': [{'name': 'Entry with private semantics', 'color': '#123456', 'expression': '5', 'semantics': {'id': sem.id, 'name': sem.name}}]}
        response = self.client.patch(url, json.dumps(data), format='json', content_type='application/json')

        # Request is successful but no new entry has been created.
        # The serializer fails silently to not loose other data while
        # creating objects. This needs to be well documented.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(entires_count, leg.legendentry_set.count())
