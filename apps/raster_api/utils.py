import os

from django.conf import settings
from django.utils import timezone
from PIL import Image, ImageDraw


def expired(token):
    """
    Verify the token expiry date.
    """
    return timezone.now() > token.expiration_date


def get_empty_tile(zoom=None, zoom_limit=None, mode='Min'):
    """
    Create an empty tile for TMS requests that do not match any data.
    """
    # Open the ref image.
    img = Image.open(os.path.join(settings.BASE_DIR, 'apps/raster_api/assets/tesselo_empty.png'))

    # Create zoom message.
    if zoom is None:
        msg = 'No Data'
    else:
        msg = 'Zoom is {}'.format(zoom)

    if zoom_limit is not None:
        msg += ' | {} zoom is {}'.format(mode, zoom_limit)

    # Write zoom message into image.
    draw = ImageDraw.Draw(img)
    text_width, text_height = draw.textsize(msg)
    draw.text(((img.width - text_width) / 2, 60 + (img.height - text_height) / 2), msg, fill='black')

    return img
