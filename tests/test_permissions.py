from __future__ import unicode_literals

from raster.models import Legend
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from django.contrib.auth.models import Group, User
from django.core.urlresolvers import reverse
from django.test import TestCase
from guardian.shortcuts import assign_perm
from raster_api.models import PublicLegend
from raster_api.views import LegendViewSet


class PermissionsTests(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()

        self.lucille = User.objects.create_user(
            username='lucille',
            email='lucille@bluth.com',
            password='bananastand'
        )

        self.michael = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )

        self.gene = User.objects.create_user(
            username='parmegian',
            email='gene@parmegian.com',
            password='cheese'
        )

        self.anyang = User.objects.create_user(
            username='anyang',
            email='anyang@example.com',
            password='anyang'
        )

        self.group = Group.objects.create(name='Bluth Family')
        self.group.user_set.add(self.michael, self.lucille)

        # Create legends.
        self.legend_no_one = Legend.objects.create(title="Private")

        self.legend_public = Legend.objects.create(title='Public')
        PublicLegend.objects.create(public=True, legend=self.legend_public)

        self.legend_michael = Legend.objects.create(title='Michaels Legend')
        assign_perm('view_legend', self.michael, self.legend_michael)

        self.legend_gene = Legend.objects.create(title='genes Legend')
        assign_perm('view_legend', self.gene, self.legend_gene)

        self.legend_group = Legend.objects.create(title='Bluth Family Legend')
        assign_perm('view_legend', self.group, self.legend_group)

    def test_legend_list_permissions(self):
        view = LegendViewSet.as_view(actions={'get': 'list'})

        url = reverse('legend-list')
        request = self.factory.get(url)

        # Unauthorized response when not authenticated.
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Show public object for anyang.
        force_authenticate(request, user=self.anyang)
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['id'], self.legend_public.id)

        # Show public and private object for gene.
        force_authenticate(request, user=self.gene)
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(response.data['results'][0]['id'], self.legend_public.id)
        self.assertEqual(response.data['results'][1]['id'], self.legend_gene.id)

        # Show public, private and group object for michael.
        force_authenticate(request, user=self.michael)
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 3)
        self.assertEqual(response.data['results'][0]['id'], self.legend_public.id)
        self.assertEqual(response.data['results'][1]['id'], self.legend_michael.id)
        self.assertEqual(response.data['results'][2]['id'], self.legend_group.id)

        # Show public and group object for lucille.
        force_authenticate(request, user=self.lucille)
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(response.data['results'][0]['id'], self.legend_public.id)
        self.assertEqual(response.data['results'][1]['id'], self.legend_group.id)

    def test_legend_detail_read_permissions(self):
        view = LegendViewSet.as_view(actions={'get': 'retrieve'})

        url = reverse('legend-detail', kwargs={'pk': self.legend_no_one.id})
        request = self.factory.get(url)

        # Unauthorized response when not authenticated.
        response = view(request)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Michael tries to see a legend without permissions.
        request = self.factory.get(url)
        force_authenticate(request, user=self.michael)
        response = view(request, pk=self.legend_no_one.id)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Michael can see his legend.
        url = reverse('legend-detail', kwargs={'pk': self.legend_michael.id})
        request = self.factory.get(url)
        force_authenticate(request, user=self.michael)
        response = view(request, pk=self.legend_michael.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.legend_michael.id)

        # Michael can see a group legend.
        url = reverse('legend-detail', kwargs={'pk': self.legend_group.id})
        request = self.factory.get(url)
        force_authenticate(request, user=self.michael)
        response = view(request, pk=self.legend_group.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.legend_group.id)

        # Anyang tries to see a group legend without permissions.
        force_authenticate(request, user=self.anyang)
        response = view(request, pk=self.legend_group.id)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Anyang sees a public legend without direct permissions.
        url = reverse('legend-detail', kwargs={'pk': self.legend_public.id})
        request = self.factory.get(url)
        force_authenticate(request, user=self.anyang)
        response = view(request, pk=self.legend_public.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.legend_public.id)

    def test_legend_detail_update_permissions(self):
        view = LegendViewSet.as_view(actions={'patch': 'update'})

        url = reverse('legend-detail', kwargs={'pk': self.legend_michael.id})
        request = self.factory.patch(url, {'title': 'Michaels New Title'})
        force_authenticate(request, user=self.michael)

        # Michael tries to update his legend without having permission.
        response = view(request, pk=self.legend_michael.id)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Michael can change see his legend after getting permission.
        assign_perm('change_legend', self.michael, self.legend_michael)
        response = view(request, pk=self.legend_michael.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Michaels New Title')

        # Michael tries to update the group legend without having permission.
        url = reverse('legend-detail', kwargs={'pk': self.legend_group.id})
        request = self.factory.patch(url, {'title': 'Michaels New Title'})
        force_authenticate(request, user=self.michael)

        response = view(request, pk=self.legend_group.id)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Add change permission to group
        assign_perm('change_legend', self.group, self.legend_group)

        # Michael can change see his legend after getting permission through group.
        response = view(request, pk=self.legend_group.id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Michaels New Title')

    def test_legend_detail_delete_permissions(self):
        view = LegendViewSet.as_view(actions={'delete': 'destroy'})

        url = reverse('legend-detail', kwargs={'pk': self.legend_michael.id})
        request = self.factory.delete(url)
        force_authenticate(request, user=self.michael)

        # Michael tries to delete his legend without having permission.
        response = view(request, pk=self.legend_michael.id)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Michael can delete his legend after getting permission.
        assign_perm('delete_legend', self.michael, self.legend_michael)
        response = view(request, pk=self.legend_michael.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Legend.objects.filter(id=self.legend_michael.id).exists())

        # Michael tries to update the group legend without having permission.
        url = reverse('legend-detail', kwargs={'pk': self.legend_group.id})
        request = self.factory.delete(url)
        force_authenticate(request, user=self.michael)

        response = view(request, pk=self.legend_group.id)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Add change permission to group
        assign_perm('delete_legend', self.group, self.legend_group)

        # Michael can change see his legend after getting permission through group.
        response = view(request, pk=self.legend_group.id)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Legend.objects.filter(id=self.legend_group.id).exists())

    def test_legend_change_permissions_permissions(self):
        self.client.login(username='michael', password='bananastand')
        url = reverse(
            'legend-(?P<act>invite|exclude)/(?P<mod>user|group)/(?P<per>view|change|delete)/(?P<inv>[0-9]+)',
            kwargs={'pk': self.legend_michael.id, 'act': 'invite', 'mod': 'user', 'per': 'view', 'inv': self.lucille.id},
        )
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Michael can invite to his legend after getting permission.
        # To invite people, one needs to have the delete permission.
        self.assertFalse(self.lucille.has_perm('view_legend', self.legend_michael))
        assign_perm('delete_legend', self.michael, self.legend_michael)
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(self.lucille.has_perm('view_legend', self.legend_michael))

        # Michael can exclude access to his legend after getting permission.
        url = reverse(
            'legend-(?P<act>invite|exclude)/(?P<mod>user|group)/(?P<per>view|change|delete)/(?P<inv>[0-9]+)',
            kwargs={'pk': self.legend_michael.id, 'act': 'exclude', 'mod': 'user', 'per': 'view', 'inv': self.lucille.id},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(self.lucille.has_perm('view_legend', self.legend_michael))
