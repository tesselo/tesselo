from guardian.admin import GuardedModelAdmin

from classify.models import (
    Classifier, ClassifierAccuracy, PredictedLayer, PredictedLayerChunk, TrainingLayer, TrainingLayerExport,
    TrainingSample
)
from django import forms
from django.contrib.gis import admin
from sentinel import const, ecs
from sentinel.models import CompositeBand, SentinelTileBand


class TrainingSampleForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(TrainingSampleForm, self).__init__(*args, **kwargs)
        if hasattr(self, 'instance'):
            if self.instance.composite:
                try:
                    red = self.instance.composite.compositeband_set.get(band=const.BD4).rasterlayer_id
                    green = self.instance.composite.compositeband_set.get(band=const.BD3).rasterlayer_id
                    blue = self.instance.composite.compositeband_set.get(band=const.BD2).rasterlayer_id
                except CompositeBand.DoesNotExist:
                    return
            elif self.instance.sentineltile:
                try:
                    red = self.instance.sentineltile.sentineltileband_set.get(band=const.BD4).layer_id
                    green = self.instance.sentineltile.sentineltileband_set.get(band=const.BD3).layer_id
                    blue = self.instance.sentineltile.sentineltileband_set.get(band=const.BD2).layer_id
                except SentinelTileBand.DoesNotExist:
                    return
            else:
                return
            url = '/api/algebra/${z}/${x}/${y}.png?' + 'layers=r={red},g={green},b={blue}&scale=0,4e3&alpha&enhance_brightness=1.6&enhance_sharpness=1.2&enhance_color=1.2&enhance_contrast=1.1'.format(
                red=red, green=green, blue=blue
            )
            if 'geom' in self.fields:
                self.fields['geom'].widget.params['tileurl'] = url


class TrainingSampleAdmin(admin.OSMGeoAdmin):
    map_template = 'classify/osm.html'
    raw_id_fields = ('composite', 'sentineltile', )
    form = TrainingSampleForm


class TrainingSampleInline(admin.TabularInline):
    model = TrainingSample
    readonly_fields = ('id', 'composite', 'sentineltile', )
    exclude = ('geom', )
    form = TrainingSampleForm

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False


class TrainingLayerAdmin(GuardedModelAdmin):
    inlines = (TrainingSampleInline, )
    readonly_fields = ('legend', )


class ClassifierAccuracyInline(admin.TabularInline):
    model = ClassifierAccuracy
    readonly_fields = ('accuracy_matrix', 'cohen_kappa', 'accuracy_score', )


class ClassifierAdmin(GuardedModelAdmin):
    inlines = (ClassifierAccuracyInline, )

    actions = ['train_classifier', ]

    readonly_fields = ['trained', ]

    raw_id_fields = ('traininglayer', 'sentineltile', )

    def train_classifier(self, request, queryset):
        """
        Admin action to train classifiers.
        """
        for clf in queryset:
            clf.status = clf.PENDING
            clf.save()
            ecs.train_sentinel_classifier(clf.id)
        self.message_user(request, 'Started training classifiers.')


class PredictedLayerAdmin(GuardedModelAdmin):
    raw_id_fields = ('composite', 'sentineltile', 'rasterlayer', )
    actions = ['predict_layer', ]

    def predict_layer(self, request, queryset):
        for pred in queryset:
            pred.write('Scheduled layer prediction', pred.PENDING)
            ecs.predict_sentinel_layer(pred.id)
        self.message_user(request, 'Started predicting layer.')


class PredictedLayerChunkAdmin(admin.ModelAdmin):
    list_filter = ('status', )
    actions = ('predict_chunk', )

    def predict_chunk(self, request, queryset):
        for chunk in queryset:
            chunk.status = chunk.PENDING
            chunk.save()
            ecs.predict_sentinel_chunk(chunk.id)
        self.message_user(request, 'Started predicting chunk.')


class TrainingLayerExportAdmin(GuardedModelAdmin):
    raw_id_fields = ('sentineltile', 'composite', )
    actions = ['export_layer', ]

    def export_layer(self, request, queryset):
        for exp in queryset:
            ecs.export_training_data(exp.id)
        self.message_user(request, 'Exporting layers.')


admin.site.register(Classifier, ClassifierAdmin)
admin.site.register(TrainingLayer, TrainingLayerAdmin)
admin.site.register(TrainingLayerExport, TrainingLayerExportAdmin)
admin.site.register(TrainingSample, TrainingSampleAdmin)
admin.site.register(PredictedLayer, PredictedLayerAdmin)
admin.site.register(PredictedLayerChunk, PredictedLayerChunkAdmin)
