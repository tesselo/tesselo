from django.contrib.gis import admin
from guardian.admin import GuardedModelAdmin

from userinterface.models import Bookmark, BookmarkFolder

admin.site.register(Bookmark, GuardedModelAdmin)
admin.site.register(BookmarkFolder, GuardedModelAdmin)
