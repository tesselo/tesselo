import json

from guardian.shortcuts import assign_perm
from raster.models import RasterLayer
from rest_framework import status

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from formulary.models import Formula, WMTSLayer
from sentinel.const import BD2, BD3, BD4
from sentinel.models import MGRSTile, SentinelTile, SentinelTileBand


class WMTSViewTests(TestCase):

    def setUp(self):

        self.usr = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )
        self.client.login(username='michael', password='bananastand')

        mgrstile = MGRSTile.objects.create(utm_zone='AA', latitude_band='2', grid_square='AA',)
        stile = SentinelTile.objects.create(
            prefix='test',
            datastrip='test',
            product_name='test',
            mgrstile=mgrstile,
            collected='2018-01-01',
            cloudy_pixel_percentage=0.95,
            data_coverage_percentage=100,
        )
        SentinelTileBand.objects.create(
            tile=stile,
            band=BD2,
            layer=RasterLayer.objects.create(),
        )
        SentinelTileBand.objects.create(
            tile=stile,
            band=BD3,
            layer=RasterLayer.objects.create(),
        )
        SentinelTileBand.objects.create(
            tile=stile,
            band=BD4,
            layer=RasterLayer.objects.create(),
        )

        self.wmtslayer = WMTSLayer.objects.create(
            title='Sudden Valley',
            sentineltile=stile,
        )

    def test_wmts_api(self):
        url = reverse('wmtslayer-list')

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 0)

        assign_perm('view_wmtslayer', self.usr, self.wmtslayer)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['results'][0]['title'], 'Sudden Valley')

    def test_wmts_service_default_rgb(self):
        url = reverse('wmts-service')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('Sudden Valley', response.content.decode())

        assign_perm('view_wmtslayer', self.usr, self.wmtslayer)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Sudden Valley', response.content.decode())

    def test_wmts_service_default_formula(self):
        self.wmtslayer.formula = Formula.objects.create(
            name='Band 4',
            formula='2 * B4',
            min_val=0,
            max_val=1e4,
        )
        self.wmtslayer.save()

        url = reverse('wmts-service')

        assign_perm('view_wmtslayer', self.usr, self.wmtslayer)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Sudden Valley', response.content.decode())
