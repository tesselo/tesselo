import json

from guardian.shortcuts import assign_perm
from raster.models import RasterLayer
from rest_framework import status

from classify.models import PredictedLayer
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from formulary.models import Formula
from raster_api.const import GET_QUERY_PARAMETER_AUTH_KEY
from raster_api.models import ReadOnlyToken
from sentinel.const import BD2, BD3, BD4
from sentinel.models import Composite, MGRSTile, SentinelTile, SentinelTileBand
from wmts.models import WMTSLayer


class WMTSViewTests(TestCase):

    def setUp(self):

        self.usr = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )
        self.client.login(username='michael', password='bananastand')

        mgrstile = MGRSTile.objects.create(utm_zone='AA', latitude_band='2', grid_square='AA',)

        self.formula = Formula.objects.create(
            name='Band 4',
            formula='2 * B4',
            min_val=0,
            max_val=1e4,
        )

        self.stile = SentinelTile.objects.create(
            prefix='test',
            datastrip='test',
            product_name='test',
            mgrstile=mgrstile,
            collected='2018-01-01',
            cloudy_pixel_percentage=0.95,
            data_coverage_percentage=100,
        )
        SentinelTileBand.objects.create(
            tile=self.stile,
            band=BD2,
            layer=RasterLayer.objects.create(),
        )
        SentinelTileBand.objects.create(
            tile=self.stile,
            band=BD3,
            layer=RasterLayer.objects.create(),
        )
        SentinelTileBand.objects.create(
            tile=self.stile,
            band=BD4,
            layer=RasterLayer.objects.create(),
        )

        self.wmtslayer1 = WMTSLayer.objects.create(
            title='Sudden Valley RGB',
            sentineltile=self.stile,
        )
        self.wmtslayer2 = WMTSLayer.objects.create(
            title='Sudden Valley Formula',
            sentineltile=self.stile,
            formula=self.formula,
        )

        composite = Composite.objects.create(
            name='Shuturmurg',
            min_date='2001-01-01',
            max_date='2001-01-31',
        )

        self.wmtslayer3 = WMTSLayer.objects.create(
            title='Shuturmurg RGB',
            composite=composite,
        )
        self.wmtslayer4 = WMTSLayer.objects.create(
            title='Shuturmurg Formula',
            composite=composite,
            formula=self.formula,
        )

        self.pred = PredictedLayer.objects.create(composite=composite)
        self.wmtslayer5 = WMTSLayer.objects.create(
            title='Shuturmurg Classified',
            predictedlayer=self.pred,
        )

        self.url = reverse('wmts-service')

    def test_wmts_api(self):
        url = reverse('wmtslayer-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 0)

        assign_perm('view_wmtslayer', self.usr, self.wmtslayer1)

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        result = json.loads(response.content.decode())
        self.assertEqual(result['count'], 1)
        self.assertEqual(result['results'][0]['title'], 'Sudden Valley RGB')

    def test_wmts_service_scene_rgb(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('Sudden Valley RGB', response.content.decode())

        assign_perm('view_wmtslayer', self.usr, self.wmtslayer1)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Sudden Valley RGB', response.content.decode())
        self.assertIn(
            'https://testserver/api/algebra/{TileMatrix}/{TileCol}/{TileRow}.png?layers=r=',
            response.content.decode(),
        )

    def test_wmts_service_scene_formula(self):
        assign_perm('view_wmtslayer', self.usr, self.wmtslayer2)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Sudden Valley Formula', response.content.decode())
        self.assertIn(
            'https://testserver/api/formula/{}/scene/{}/{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png'.format(
                self.formula.id,
                self.stile.id,
            ),
            response.content.decode(),
        )

    def test_wmts_service_composite_rgb(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn('Shuturmurg RGB', response.content.decode())

        assign_perm('view_wmtslayer', self.usr, self.wmtslayer3)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Shuturmurg RGB', response.content.decode())

    def test_wmts_service_composite_formula(self):
        assign_perm('view_wmtslayer', self.usr, self.wmtslayer4)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Shuturmurg Formula', response.content.decode())

    def test_wmts_service_predicted_layer(self):
        assign_perm('view_wmtslayer', self.usr, self.wmtslayer5)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Shuturmurg Classified', response.content.decode())
        self.assertIn('/tile/{}/'.format(self.pred.rasterlayer_id), response.content.decode())

    def test_wmts_read_only_auth_key(self):
        self.client.logout()
        assign_perm('view_wmtslayer', self.usr, self.wmtslayer2)
        token = ReadOnlyToken.objects.create(user=self.usr)
        url = self.url + '?{}={}'.format(GET_QUERY_PARAMETER_AUTH_KEY, token.key)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('Sudden Valley Formula', response.content.decode())
        self.assertIn(
            'https://testserver/api/formula/{}/scene/{}/{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png'.format(
                self.formula.id,
                self.stile.id,
            ),
            response.content.decode(),
        )
