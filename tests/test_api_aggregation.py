from guardian.shortcuts import assign_perm
from numpy.testing import assert_almost_equal
from raster_aggregation.models import AggregationArea, AggregationLayer

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(CELERY_TASK_ALWAYS_EAGER=True)
class AggregationViewTests(TestCase):

    def setUp(self):

        self.usr = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )
        self.client.login(username='michael', password='bananastand')

        self.agglayer = AggregationLayer.objects.create(
            name='Near bananastand.',
            description='An arrested testfile.',
            name_column='test',
        )
        self.aggarea = AggregationArea.objects.create(
            name='Testarea',
            aggregationlayer=self.agglayer,
            geom='SRID=4326;MULTIPOLYGON (((30 20, 45 40, 10 40, 30 20)),((15 5, 40 10, 10 20, 5 10, 15 5)))',
        )

    def test_list_aggregation_layers(self):
        self.maxDiff = None
        url = reverse('aggregationlayer-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertDictEqual(
            response.json(),
            {'count': 0, 'next': None, 'previous': None, 'results': []},
        )

        assign_perm('view_aggregationlayer', self.usr, self.agglayer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        extent = result['results'][0].pop('extent')
        self.assertDictEqual(
            result,
            {
                'count': 1,
                'next': None,
                'previous': None,
                'results': [
                    {
                        'id': self.agglayer.id,
                        'description': 'An arrested testfile.',
                        'max_zoom_level': 18,
                        'min_zoom_level': 0,
                        'name': 'Near bananastand.',
                        'nr_of_areas': 1,
                        'shapefile': '',
                        'name_column': 'test',
                        'parse_log': '',
                        'status': 'Unprocessed',
                    }
                ]
            },
        )
        assert_almost_equal(extent, [5, 5, 45, 40])

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

    def test_update_extent(self):
        # Current extent is inexistent.
        self.assertIsNone(self.agglayer.extent)
        # Add new area.
        AggregationArea.objects.create(
            name='Testarea new extent',
            aggregationlayer=self.agglayer,
            geom='SRID=4326;MULTIPOLYGON (((30 20, 45 40, 10 40, 30 20)),((15 4, 40 10, 10 20, 5 10, 15 4)))',
        )
        # Update extent url.
        url = reverse('aggregationlayer-detail', kwargs={'pk': self.agglayer.id})
        # Allow user to change extent.
        assign_perm('view_aggregationlayer', self.usr, self.agglayer)
        assign_perm('add_aggregationlayer', self.usr, self.agglayer)
        # Request extent update.
        response = self.client.post(url + '/update_extent')
        self.assertEqual(response.status_code, 200)
        # Extent has been updated.
        self.agglayer.refresh_from_db()
        assert_almost_equal(
            self.agglayer.extent.extent,
            (556597.453966367, 445640.109656027, 5009377.08569731, 4865942.27950318),
        )
