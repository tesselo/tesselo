from storages.backends.s3boto3 import S3Boto3Storage

from django.conf import settings
from django.core.files.storage import get_storage_class


class StaticRootCachedS3Boto3Storage(S3Boto3Storage):
    """
    S3 storage backend that saves the files locally, too. This is to know
    which compressed files were already uploaded.
    """
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME_STATIC
    preload_metadata = True
    querystring_auth = False
    default_acl = 'public-read'

    def __init__(self, *args, **kwargs):
        super(StaticRootCachedS3Boto3Storage, self).__init__(*args, **kwargs)

        self.local_storage = get_storage_class(
            "compressor.storage.CompressorFileStorage")()

    def save(self, name, content):
        self.local_storage._save(name, content)
        super(StaticRootCachedS3Boto3Storage, self).save(name, self.local_storage._open(name))
        return name


class PrivateMediaS3Boto3Storage(S3Boto3Storage):
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME_MEDIA
    default_acl = 'private'
    file_overwrite = True
    signature_version = 's3v4'
