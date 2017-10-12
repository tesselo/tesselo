from swift.storage import StaticSwiftStorage

from django.core.files.storage import get_storage_class


class CachedStaticSwiftStorage(StaticSwiftStorage):
    """
    Swift storage backend that saves the files locally, too. This is to know
    which compressed files were already uploaded.
    """
    def __init__(self, *args, **kwargs):
        super(CachedStaticSwiftStorage, self).__init__(*args, **kwargs)
        self.local_storage = get_storage_class(
            "compressor.storage.CompressorFileStorage"
        )()

    def save(self, name, content):
        self.local_storage._save(name, content)
        super(CachedStaticSwiftStorage, self).save(name, self.local_storage._open(name))
        return name


def debug_tag(context):
    return {'DEBUG': True}
