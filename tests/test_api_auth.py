from rest_framework import status
from rest_framework.authtoken.models import Token

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from raster_api.models import TesseloUserAccount
from raster_api.utils import expired


class ApiAuthViewTests(TestCase):

    def setUp(self):
        self.usr = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )
        self.login_url = reverse('api-token-auth')
        self.logout_url = reverse('api-token-logout')

    def test_login(self):
        profile = {'baselayers': 'openlayers.org'}
        TesseloUserAccount.objects.create(
            user=self.usr,
            profile=profile,
        )
        # Login.
        response = self.client.post(self.login_url, data={'username': 'michael', 'password': 'bananastand'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Token.objects.filter(user=self.usr).exists())
        self.assertDictEqual(response.json()['profile'], profile)

    def test_logout(self):
        # Unauthorized logout.
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Get token.
        response = self.client.post(self.login_url, data={'username': 'michael', 'password': 'bananastand'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Token.objects.filter(user=self.usr).exists())
        self.assertDictEqual(response.json()['profile'], {})

        # Use token to logout via POST.
        token = response.json()['token']
        headers = {'HTTP_AUTHORIZATION': 'Token {}'.format(token)}
        response = self.client.post(self.logout_url, {}, **headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(user=self.usr).exists())

    def test_token_expired(self):
        # A new token is valid.
        token = Token.objects.create(user=self.usr)
        self.assertFalse(expired(token))
        # An old token is expired.
        token.created = timezone.datetime(2017, 1, 1)
        token.save()
        token.refresh_from_db()
        self.assertTrue(expired(token))

    def test_token_expired_api(self):
        token = Token.objects.create(user=self.usr)
        token.created = timezone.datetime(2017, 1, 1)
        token.save()
        token.refresh_from_db()
        headers = {'HTTP_AUTHORIZATION': 'Token {}'.format(token)}
        response = self.client.post(self.logout_url, {}, **headers)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refreshed_on_auth(self):
        # Manually expire the token.
        token = Token.objects.create(user=self.usr)
        token.created = timezone.datetime(2017, 1, 1)
        token.save()
        token.refresh_from_db()
        self.assertTrue(expired(token))
        # Post to the token auth url, this should return a fresh token.
        response = self.client.post(self.login_url, data={'username': 'michael', 'password': 'bananastand'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        token = Token.objects.get(user=self.usr)
        self.assertFalse(expired(token))
        self.assertIn('expires', response.json())
