from rest_framework import status
from rest_framework.exceptions import APIException


class MissingZoomLevel(APIException):
    default_detail = 'Zoom level could not be determined. Please provide as input parameter.'
    status_code = status.HTTP_400_BAD_REQUEST
