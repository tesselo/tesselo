from guardian.admin import GuardedModelAdmin

from django.contrib.gis import admin
from formulary.models import Formula, PredictedLayerFormula


class PredictedLayerFormulaInline(admin.TabularInline):
    model = PredictedLayerFormula
    raw_id_fields = ('predictedlayer', )
    extra = 0


class FormulaAdmin(GuardedModelAdmin):
    model = Formula
    search_fields = ('name', 'acronym', 'description', )
    list_filter = ('rgb', )
    inlines = (PredictedLayerFormulaInline, )


admin.site.register(Formula, FormulaAdmin)
