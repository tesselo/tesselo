from storages.backends.s3boto3 import S3Boto3Storage

from django.conf import settings
from django.core.files.storage import get_storage_class


class StaticRootS3Boto3Storage(S3Boto3Storage):
    """
    S3 storage backend for static files.
    """
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME_STATIC
    preload_metadata = True
    querystring_auth = False
    default_acl = 'public-read'


class PrivateMediaS3Boto3Storage(S3Boto3Storage):
    """
    S3 storage backend for media files.
    """
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME_MEDIA
    default_acl = 'private'
    file_overwrite = True
    signature_version = 's3v4'
