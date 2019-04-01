from guardian.admin import GuardedModelAdmin

from django.contrib.gis import admin
from userinterface.models import Bookmark, BookmarkFolder

admin.site.register(Bookmark, GuardedModelAdmin)
admin.site.register(BookmarkFolder, GuardedModelAdmin)
