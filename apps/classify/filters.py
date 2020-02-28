from django_filters.rest_framework import FilterSet, NumberFilter

from classify.models import PredictedLayer


class PredictedLayerFilter(FilterSet):

    year = NumberFilter(label='Year', field_name='min_date__year')

    class Meta:
        model = PredictedLayer
        fields = ['year', 'aggregationlayer', 'classifier', 'sentineltile', ]
