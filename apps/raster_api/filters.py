from django_filters.rest_framework import FilterSet, NumberFilter

from sentinel.models import Composite, SentinelTileAggregationLayer


class CompositeFilter(FilterSet):

    year = NumberFilter(name='min_date', method='year_filter', label='Filter by year')

    class Meta:
        model = Composite
        fields = ('active', 'official', 'interval', 'year', )

    def year_filter(self, queryset, name, value):
        return queryset.filter(**{
            'min_date__year': value,
        })


class SentinelTileAggregationLayerFilter(FilterSet):

    year = NumberFilter(name='sentineltile', method='year_filter', label='Filter by year')

    class Meta:
        model = SentinelTileAggregationLayer
        fields = ('active', 'aggregationlayer', 'year', )

    def year_filter(self, queryset, name, value):
        return queryset.filter(**{
            'sentineltile__collected__year': value,
        })
