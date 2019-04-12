from raster_api.serializers import PermissionsModelSerializer
from userinterface.models import Bookmark, BookmarkFolder


class BookmarkSerializer(PermissionsModelSerializer):

    class Meta:
        model = Bookmark
        fields = (
            'id', 'name', 'description', 'url', 'bookmarkfolder', 'created',
        )


class BookmarkFolderSerializer(PermissionsModelSerializer):

    bookmarks = BookmarkSerializer(many=True, source='bookmark_set')

    class Meta:
        model = BookmarkFolder
        fields = (
            'id', 'name', 'description', 'bookmarks',
        )
        read_only_fields = ('bookmarks', )
