from guardian.shortcuts import assign_perm
from rest_framework import status

from classify.models import PredictedLayer
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from formulary.models import Formula
from raster_api.const import GET_QUERY_PARAMETER_AUTH_KEY
from raster_api.models import ReadOnlyToken
from sentinel.models import Composite


class WMTSViewTests(TestCase):

    def setUp(self):

        self.usr = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )
        self.client.login(username='michael', password='bananastand')

        self.formula = Formula.objects.create(
            name='Band 4',
            acronym='B4',
            formula='2 * B4',
            min_val=0,
            max_val=1e4,
        )
        self.formula_rgb = Formula.objects.create(name='Banana RGB', rgb=True)

        self.composite = Composite.objects.create(
            name='Shuturmurg',
            min_date='2001-01-01',
            max_date='2001-01-31',
        )
        self.composite_future = Composite.objects.create(
            name='Shuturmurg Future',
            min_date='3001-01-01',
            max_date='3001-01-31',
        )

        self.pred = PredictedLayer.objects.create(composite=self.composite)

        self.url = reverse('wmts-service')

    def test_wmts_service_composite_formula(self):
        title = '{} | {} - {}'.format(self.composite.name, self.formula.acronym, self.formula.name)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(title, response.content.decode())

        assign_perm('view_formula', self.usr, self.formula)
        assign_perm('view_composite', self.usr, self.composite)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(title, response.content.decode())
        self.assertIn(
            'https://testserver/formula/{}/composite/{}/{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png'.format(
                self.formula.id,
                self.composite.id,
            ),
            response.content.decode(),
        )

    def test_wmts_service_composite_formula_rgb(self):
        title = '{} | {} - {}'.format(self.composite.name, self.formula_rgb.acronym, self.formula_rgb.name)
        assign_perm('view_formula', self.usr, self.formula_rgb)
        assign_perm('view_composite', self.usr, self.composite)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(title, response.content.decode())
        self.assertIn(
            'https://testserver/formula/{}/composite/{}/{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png'.format(
                self.formula_rgb.id,
                self.composite.id,
            ),
            response.content.decode(),
        )

    def test_wmts_service_predicted_layer(self):
        title = '{}'.format(self.pred)

        assign_perm('view_predictedlayer', self.usr, self.pred)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(title, response.content.decode())
        self.assertIn('/tile/{}/'.format(self.pred.rasterlayer_id), response.content.decode())

    def test_wmts_read_only_auth_key(self):
        self.client.logout()
        title = '{} | {} - {}'.format(self.composite.name, self.formula.acronym, self.formula.name)

        assign_perm('view_formula', self.usr, self.formula)
        assign_perm('view_composite', self.usr, self.composite)

        token = ReadOnlyToken.objects.create(user=self.usr)

        url = self.url + '?{}={}'.format(GET_QUERY_PARAMETER_AUTH_KEY, token.key)

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(title, response.content.decode())
        self.assertIn(
            'https://testserver/formula/{}/composite/{}/{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png'.format(
                self.formula.id,
                self.composite.id,
            ),
            response.content.decode(),
        )

    def test_wmts_service_composite_future(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        assign_perm('view_formula', self.usr, self.formula)
        assign_perm('view_composite', self.usr, self.composite_future)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertNotIn(
            'https://testserver/formula/{}/composite/{}/{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png'.format(
                self.formula.id,
                self.composite_future.id,
            ),
            response.content.decode(),
        )
