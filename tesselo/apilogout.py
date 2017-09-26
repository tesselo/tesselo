
from rest_framework import renderers
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView


class RemoveAuthToken(APIView):
    renderer_classes = (renderers.JSONRenderer,)

    def get(self, request, *args, **kwargs):
        Token.objects.filter(user=request.user).delete()
        return Response({'logout': 'Successfully logged out.'})

    def post(self, request, *args, **kwargs):
        """
        Logout may be done via POST.
        """
        return self.get(request, *args, **kwargs)


remove_auth_token = RemoveAuthToken.as_view()
