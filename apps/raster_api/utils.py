
from datetime import timedelta

from django.utils import timezone

EXPIRING_TOKEN_LIFESPAN = timedelta(days=14)


def expired(token):
    """
    Verify the token expiry date.
    """
    return timezone.now() - token.created >= EXPIRING_TOKEN_LIFESPAN
