
from rest_framework import renderers
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView


class RemoveAuthToken(APIView):
    """
    Destroy auth token of the user by sending a POST request to this url.
    """
    renderer_classes = (renderers.JSONRenderer,)

    def post(self, request, *args, **kwargs):
        Token.objects.filter(user=request.user).delete()
        return Response({'logout': 'Successfully logged out.'})


remove_auth_token = RemoveAuthToken.as_view()
