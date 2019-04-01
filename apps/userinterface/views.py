# Create your views here.
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter

from raster_api.views import PermissionsModelViewSet
from userinterface.models import Bookmark, BookmarkFolder
from userinterface.serializers import BookmarkFolderSerializer, BookmarkSerializer


class BookmarkViewSet(PermissionsModelViewSet):
    queryset = Bookmark.objects.all().order_by('name')
    serializer_class = BookmarkSerializer
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    search_fields = ('name', 'description')
    _model = 'bookmark'


class BookmarkFolderViewSet(PermissionsModelViewSet):
    queryset = BookmarkFolder.objects.all().order_by('name')
    serializer_class = BookmarkFolderSerializer
    filter_backends = (SearchFilter, DjangoFilterBackend, )
    search_fields = ('name', 'description')
    _model = 'bookmarkfolder'
