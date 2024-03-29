from django import forms
from django.contrib.gis import admin
from guardian.admin import GuardedModelAdmin

from classify.models import (
    Classifier, ClassifierAccuracy, PredictedLayer, PredictedLayerChunk, TrainingLayer, TrainingPixels,
    TrainingPixelsPatch, TrainingSample
)
from jobs import ecs
from sentinel import const
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
            url = '/algebra/${z}/${x}/${y}.png?' + 'layers=r={red},g={green},b={blue}&scale=0,1e4&alpha&enhance_brightness=3.0&enhance_sharpness=1.2&enhance_color=1.9&enhance_contrast=1.5'.format(
                red=red, green=green, blue=blue
            )
            if 'geom' in self.fields:
                self.fields['geom'].widget.params['tileurl'] = url


class TrainingSampleAdmin(admin.OSMGeoAdmin):
    map_template = 'classify/osm.html'
    raw_id_fields = ('composite', 'sentineltile', )
    search_fields = ('date', 'category')
    form = TrainingSampleForm


class TrainingLayerAdmin(GuardedModelAdmin):
    readonly_fields = ('legend', )


class ClassifierAccuracyInline(admin.TabularInline):
    model = ClassifierAccuracy
    readonly_fields = ('accuracy_matrix', 'cohen_kappa', 'accuracy_score', )


class ClassifierAdmin(GuardedModelAdmin):
    inlines = (ClassifierAccuracyInline, )

    actions = ['train_classifier', ]

    readonly_fields = ['trained', ]

    raw_id_fields = ('traininglayer', 'sentineltile', 'trainingpixels', )

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
    raw_id_fields = (
        'sentineltile', 'rasterlayer', 'aggregationlayer', 'classifier',
        'sieve_parent', 'legend', 'composites',
    )
    actions = ['predict_layer', ]
    list_filter = ('status', )
    search_fields = ('name', 'classifier__name', )

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


class TrainingPixelsAdmin(admin.ModelAdmin):

    actions = ['populate_trainingpixels', 'combine_trainingpixels_patches']
    raw_id_fields = ('traininglayer', 'sentineltile', 'composites', )

    def populate_trainingpixels(self, request, queryset):
        for tp in queryset:
            tp.write('Scheduled pixel collection.', tp.PENDING)
            ecs.populate_trainingpixels(tp.id)
        self.message_user(request, 'Started populating pixels.')


class TrainingPixelsChunkAdmin(admin.ModelAdmin):
    list_filter = ('status', )


admin.site.register(Classifier, ClassifierAdmin)
admin.site.register(TrainingLayer, TrainingLayerAdmin)
admin.site.register(TrainingSample, TrainingSampleAdmin)
admin.site.register(PredictedLayer, PredictedLayerAdmin)
admin.site.register(PredictedLayerChunk, PredictedLayerChunkAdmin)
admin.site.register(TrainingPixels, TrainingPixelsAdmin)
admin.site.register(TrainingPixelsPatch, TrainingPixelsChunkAdmin)
