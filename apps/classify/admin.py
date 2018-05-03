from classify.models import Classifier, PredictedLayer, TrainingSample
from django import forms
from django.contrib.gis import admin
from sentinel import const, ecs


class TrainingSampleForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(TrainingSampleForm, self).__init__(*args, **kwargs)
        if hasattr(self, 'instance'):
            if self.instance.composite:
                red = self.instance.composite.compositeband_set.get(band=const.BD4).rasterlayer_id
                green = self.instance.composite.compositeband_set.get(band=const.BD3).rasterlayer_id
                blue = self.instance.composite.compositeband_set.get(band=const.BD2).rasterlayer_id
            elif self.instance.sentineltile:
                red = self.instance.sentineltile.sentineltileband_set.get(band=const.BD4).layer_id
                green = self.instance.sentineltile.sentineltileband_set.get(band=const.BD3).layer_id
                blue = self.instance.sentineltile.sentineltileband_set.get(band=const.BD2).layer_id
            else:
                return
            url = '/api/algebra/${z}/${x}/${y}.png?' + 'layers=r={red},g={green},b={blue}&scale=0,4e3&alpha&enhance_brightness=1.6&enhance_sharpness=1.2&enhance_color=1.2&enhance_contrast=1.1'.format(
                red=red, green=green, blue=blue
            )
            self.fields['geom'].widget.params['tileurl'] = url


class TrainingSampleAdmin(admin.OSMGeoAdmin):
    map_template = 'classify/osm.html'
    raw_id_fields = ('composite', 'sentineltile', )
    form = TrainingSampleForm


class ClassifierAdmin(admin.ModelAdmin):

    actions = ['train_classifier', ]

    def train_classifier(self, request, queryset):
        """
        Admin action to train classifiers.
        """
        for clf in queryset:
            ecs.train_sentinel_classifier(clf.id)
        self.message_user(request, 'Started training classifiers.')


class PredictedLayerAdmin(admin.ModelAdmin):
    raw_id_fields = ('composite', 'sentineltile', 'rasterlayer', )
    actions = ['predict_layer', ]

    def predict_layer(self, request, queryset):
        for pred in queryset:
            ecs.predict_sentinel_layer(pred.id)
        self.message_user(request, 'Started predicting layer.')


admin.site.register(Classifier, ClassifierAdmin)
admin.site.register(TrainingSample, TrainingSampleAdmin)
admin.site.register(PredictedLayer, PredictedLayerAdmin)
