from __future__ import unicode_literals

import tempfile
from unittest import skip

from django.contrib.auth.models import User
from django.core.files import File
from django.core.urlresolvers import reverse
from django.test import TestCase, override_settings
from guardian.shortcuts import assign_perm
from raster_aggregation.models import AggregationArea, AggregationLayer


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class AggregationViewTests(TestCase):

    def setUp(self):

        self.usr = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )
        self.client.login(username='michael', password='bananastand')

        aggfile = tempfile.NamedTemporaryFile(suffix='.zip')
        self.agglayer = AggregationLayer.objects.create(
            name='Testfile',
            name_column='test',
            shapefile=File(open(aggfile.name), name='test.shp.zip')
        )
        self.aggarea = AggregationArea.objects.create(
            name='Testarea',
            aggregationlayer=self.agglayer,
            geom='SRID=4326;MULTIPOLYGON (((30 20, 45 40, 10 40, 30 20)),((15 5, 40 10, 10 20, 5 10, 15 5)))',
        )

    @skip('Test under construction.')
    def test_list_aggregation_layers(self):
        url = reverse('aggregationlayer-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)

        response = self.client.get(url + '?aggregationlayer=23')
        self.assertEqual(response.status_code, 404)

    def test_list_aggregation_areas(self):
        url = reverse('aggregationarea-list')
        # Missing query paremeter.
        response = self.client.get(url)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.content, b'{"detail":"Missing query parameter: aggregationlayer"}')
        # Without permissions.
        response = self.client.get(url + '?aggregationlayer={0}'.format(self.agglayer.id))
        self.assertEqual(response.status_code, 404)
        # With permissions.
        assign_perm('view_aggregationlayer', self.usr, self.agglayer)
        response = self.client.get(url + '?aggregationlayer={0}'.format(self.agglayer.id))
        self.assertEqual(response.status_code, 200)
        # Unknown layer id.
        assign_perm('view_aggregationlayer', self.usr, self.agglayer)
        response = self.client.get(url + '?aggregationlayer=1234')
        self.assertEqual(response.status_code, 404)
