from guardian.admin import GuardedModelAdmin

from django.contrib.gis import admin
from formulary.models import Formula

admin.site.register(Formula, GuardedModelAdmin)
