from rest_framework import status
from rest_framework.authtoken.models import Token

from django.contrib.auth.models import User
from django.test import TestCase


class ApiLogoutViewTests(TestCase):

    def setUp(self):
        self.usr = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )

    def test_logout(self):
        # Unauthorized logout.
        response = self.client.post('/api/token-logout/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Get token.
        response = self.client.post('/api/token-auth/', data={'username': 'michael', 'password': 'bananastand'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(Token.objects.filter(user=self.usr).exists())

        # Use token to logout via POST.
        token = response.json()['token']
        headers = {'HTTP_AUTHORIZATION': 'Token {}'.format(token)}
        response = self.client.post('/api/token-logout/', {}, **headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(user=self.usr).exists())

        # Same using GET request.
        token = Token.objects.create(user=self.usr).key
        headers = {'HTTP_AUTHORIZATION': 'Token {}'.format(token)}
        response = self.client.get('/api/token-logout/', **headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(user=self.usr).exists())
