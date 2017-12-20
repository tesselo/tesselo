from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed

from raster_api.utils import expired


class ExpiringTokenAuthentication(TokenAuthentication):
    """
    Expiring token authentication.
    """
    def authenticate_credentials(self, key):
        user, token = super(ExpiringTokenAuthentication, self).authenticate_credentials(key)

        if expired(token):
            raise AuthenticationFailed('Token has expired')

        return (user, token)
