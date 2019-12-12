from guardian.admin import GuardedModelAdmin

from django.contrib.gis import admin
from formulary.models import Formula


class FormulaAdmin(GuardedModelAdmin):
    model = Formula
    search_fields = ('name', 'acronym', 'description', )
    list_filter = ('rgb', )


admin.site.register(Formula, FormulaAdmin)
