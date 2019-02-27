import json

from guardian.shortcuts import assign_perm
from raster.models import Legend, LegendEntry, LegendSemantics
from rest_framework import status
from rest_framework.test import APIRequestFactory, force_authenticate

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse
from raster_api.models import TesseloUserAccount
from raster_api.views import LegendEntryViewSet, LegendViewSet
from sentinel.models import Composite


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
        self.sem = LegendSemantics.objects.create(name='Urban')
        dat = {'color': '#123456', 'expression': '1', 'semantics': self.sem}

        self.legend_no_one = Legend.objects.create(title="Private")
        LegendEntry.objects.create(legend=self.legend_no_one, **dat)

        self.legend_public = Legend.objects.create(title='Public')
        self.legend_public.publiclegend.public = True
        self.legend_public.publiclegend.save()
        LegendEntry.objects.create(legend=self.legend_public, **dat)

        self.legend_michael = Legend.objects.create(title='Michaels Legend')
        LegendEntry.objects.create(legend=self.legend_michael, **dat)
        assign_perm('view_legend', self.michael, self.legend_michael)

        self.legend_gene = Legend.objects.create(title='genes Legend')
        LegendEntry.objects.create(legend=self.legend_gene, **dat)
        assign_perm('view_legend', self.gene, self.legend_gene)

        self.legend_group = Legend.objects.create(title='Bluth Family Legend')
        LegendEntry.objects.create(legend=self.legend_group, **dat)
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

        # Michael can change his legend after getting permission.
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
        # Use the client for this call, the factory ignores the method level
        # permissions.
        self.client.login(username='michael', password='bananastand')
        assign_perm('change_legend', self.michael, self.legend_michael)
        url = reverse(
            'legend-invite',
            kwargs={'pk': self.legend_michael.id, 'action': 'invite', 'model': 'user', 'permission': 'view', 'invitee': self.lucille.id},
        )
        response = self.client.post(url)

        # Michael can invite and exclude users or groups to his legend after
        # getting the delete permission. To invite people, one needs to have the
        # delete permission.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        assign_perm('delete_legend', self.michael, self.legend_michael)

        # Test endpoint for
        for perm in ('view', 'change', 'delete'):
            self.assertFalse(self.lucille.has_perm('{0}_legend'.format(perm), self.legend_michael))
            # Check permissions manage endpoint for users.
            url = reverse(
                'legend-invite',
                kwargs={'pk': self.legend_michael.id, 'action': 'invite', 'model': 'user', 'permission': perm, 'invitee': self.lucille.id},
            )
            response = self.client.post(url)
            # Invite User
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(self.lucille.has_perm('{0}_legend'.format(perm), self.legend_michael))
            # Exclude User
            url = reverse(
                'legend-invite',
                kwargs={'pk': self.legend_michael.id, 'action': 'exclude', 'model': 'user', 'permission': perm, 'invitee': self.lucille.id},
            )
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertFalse(self.lucille.has_perm('{0}_legend'.format(perm), self.legend_michael))

            # Check permissions manage endpoint for groups.
            # Invite group
            url = reverse(
                'legend-invite',
                kwargs={'pk': self.legend_michael.id, 'action': 'invite', 'model': 'group', 'permission': perm, 'invitee': self.group.id},
            )
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(self.lucille.has_perm('{0}_legend'.format(perm), self.legend_michael))
            # Exclude group
            url = reverse(
                'legend-invite',
                kwargs={'pk': self.legend_michael.id, 'action': 'exclude', 'model': 'group', 'permission': perm, 'invitee': self.group.id},
            )
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertFalse(self.lucille.has_perm('{0}_legend'.format(perm), self.legend_michael))

    def test_legend_toggle_public(self):
        self.client.login(username='michael', password='bananastand')
        url = reverse('legend-publish', kwargs={'pk': self.legend_michael.id})

        # Michael tries to publish his legend without having permission.
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Michael can publish his legend after getting permission.
        assign_perm('delete_legend', self.michael, self.legend_michael)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.legend_michael.publiclegend.refresh_from_db()
        self.assertTrue(self.legend_michael.publiclegend.public)
        self.assertEqual(response.data['success'], 'Made legend {} public'.format(self.legend_michael.id))

        # Michael can unpublish his legend after getting permission.
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.legend_michael.publiclegend.refresh_from_db()
        self.assertFalse(self.legend_michael.publiclegend.public)

    def test_legend_entry_read_permissions(self):
        view = LegendEntryViewSet.as_view(actions={'get': 'retrieve'})

        # Michael tries to see a legend entry from a legend without permissions.
        url = reverse('legendentry-detail', kwargs={'pk': self.legend_no_one.legendentry_set.first().id})
        request = self.factory.get(url)
        force_authenticate(request, user=self.michael)
        response = view(request, pk=self.legend_no_one.legendentry_set.first().id)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Michael tries to see a legend entry from his own legend.
        url = reverse('legendentry-detail', kwargs={'pk': self.legend_michael.legendentry_set.first().id})
        request = self.factory.get(url)
        force_authenticate(request, user=self.michael)
        response = view(request, pk=self.legend_michael.legendentry_set.first().id)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.legend_michael.legendentry_set.first().id)

    def test_composite_invite(self):
        self.world = {
            'name': 'Sentinel',
            'all_zones': False,
            'min_date': '2000-01-01',
            'max_date': '2001-01-01',
        }
        url = reverse('composite-list')
        self.client.login(username='michael', password='bananastand')
        response = self.client.post(url, json.dumps(self.world), format='json', content_type='application/json')
        self.world = Composite.objects.get(id=response.data['id'])
        self.layer = self.world.compositeband_set.first().rasterlayer
        url = reverse(
            'composite-invite',
            kwargs={'pk': self.world, 'action': 'invite', 'model': 'user', 'permission': 'view', 'invitee': self.lucille.id},
        )
        response = self.client.post(url)

        # Michael can invite and exclude users or groups to his composite after
        # getting the delete permission. To invite people, one needs to have the
        # delete permission.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        assign_perm('delete_composite', self.michael, self.world)

        # Test endpoint for
        for perm in ('view', 'change', 'delete'):
            self.assertFalse(self.lucille.has_perm('{0}_composite'.format(perm), self.world))
            self.assertFalse(self.lucille.has_perm('{0}_rasterlayer'.format(perm), self.layer))
            # Check permissions manage endpoint for users.
            url = reverse(
                'composite-invite',
                kwargs={'pk': self.world.id, 'action': 'invite', 'model': 'user', 'permission': perm, 'invitee': self.lucille.id},
            )
            response = self.client.post(url)
            # Invite User
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(self.lucille.has_perm('{0}_composite'.format(perm), self.world))
            self.assertTrue(self.lucille.has_perm('{0}_rasterlayer'.format(perm), self.layer))
            # Exclude User
            url = reverse(
                'composite-invite',
                kwargs={'pk': self.world.id, 'action': 'exclude', 'model': 'user', 'permission': perm, 'invitee': self.lucille.id},
            )
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertFalse(self.lucille.has_perm('{0}_composite'.format(perm), self.world))
            self.assertFalse(self.lucille.has_perm('{0}_rasterlayer'.format(perm), self.layer))

            # Check permissions manage endpoint for groups.
            # Invite group
            url = reverse(
                'composite-invite',
                kwargs={'pk': self.world.id, 'action': 'invite', 'model': 'group', 'permission': perm, 'invitee': self.group.id},
            )
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertTrue(self.lucille.has_perm('{0}_composite'.format(perm), self.world))
            self.assertTrue(self.lucille.has_perm('{0}_rasterlayer'.format(perm), self.layer))
            # Exclude group
            url = reverse(
                'composite-invite',
                kwargs={'pk': self.world.id, 'action': 'exclude', 'model': 'group', 'permission': perm, 'invitee': self.group.id},
            )
            response = self.client.post(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertFalse(self.lucille.has_perm('{0}_composite'.format(perm), self.world))
            self.assertFalse(self.lucille.has_perm('{0}_rasterlayer'.format(perm), self.layer))

    def test_readonly_account(self):
        # Use the client for this call, the factory ignores the method level
        # permissions.
        self.client.login(username='michael', password='bananastand')
        # Set read only flag on user account.
        account = TesseloUserAccount.objects.create(user=self.michael, read_only=True)
        # Add changing permission.
        assign_perm('change_legend', self.michael, self.legend_michael)
        # Try a post to change permisson.
        url = reverse(
            'legend-invite',
            kwargs={'pk': self.legend_michael.id, 'action': 'invite', 'model': 'user', 'permission': 'view', 'invitee': self.lucille.id},
        )
        response = self.client.post(url)
        # Ensure that the request was denied.
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Try creating object.
        self.world = {
            'name': 'Sentinel',
            'all_zones': False,
            'min_date': '2000-01-01',
            'max_date': '2001-01-01',
        }
        url = reverse('composite-list')
        self.client.login(username='michael', password='bananastand')
        response = self.client.post(url, json.dumps(self.world), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        # Change user account flag and try again.
        account.read_only = False
        account.save()
        response = self.client.post(url, json.dumps(self.world), format='json', content_type='application/json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
