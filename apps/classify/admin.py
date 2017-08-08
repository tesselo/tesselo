from classify.models import Classifier, TrainingSample
from django import forms
from django.contrib.gis import admin
from sentinel import const
from classify.tasks import train_cloud_classifier


class TrainingSmapleForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super(TrainingSmapleForm, self).__init__(*args, **kwargs)
        if hasattr(self, 'instance'):
            if self.instance.worldlayergroup:
                red = self.instance.worldlayergroup.worldlayers.get(band=const.BD4).rasterlayer_id
                green = self.instance.worldlayergroup.worldlayers.get(band=const.BD3).rasterlayer_id
                blue = self.instance.worldlayergroup.worldlayers.get(band=const.BD2).rasterlayer_id
            elif self.instance.sentineltile:
                red = self.instance.sentineltile.sentineltileband_set.get(band=const.BD4).layer_id
                green = self.instance.sentineltile.sentineltileband_set.get(band=const.BD3).layer_id
                blue = self.instance.sentineltile.sentineltileband_set.get(band=const.BD2).layer_id
            else:
                return

            url = '/api/algebra/${z}/${x}/${y}.png?' + 'layers=r={red},g={green},b={blue}&scale=3e3'.format(
                red=red, green=green, blue=blue
            )
            self.fields['geom'].widget.params['tileurl'] = url


class TrainingSampleAdmin(admin.OSMGeoAdmin):
    map_template = 'classify/osm.html'
    raw_id_fields = ('worldlayergroup', 'sentineltile', )
    form = TrainingSmapleForm


class ClassifierAdmin(admin.ModelAdmin):

    actions = ['train_classifier', ]

    def train_classifier(self, request, queryset):
        """
        Admin action to train classifiers.
        """
        for clf in queryset:
            train_cloud_classifier.delay(clf.id)
        self.message_user(request, 'Started training classifiers.')


admin.site.register(Classifier, ClassifierAdmin)
admin.site.register(TrainingSample, TrainingSampleAdmin)
