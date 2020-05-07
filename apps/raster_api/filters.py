from django_filters.rest_framework import DateFromToRangeFilter, FilterSet, NumberFilter

from sentinel.models import Composite, SentinelTileAggregationLayer


class CompositeFilter(FilterSet):

    year = NumberFilter(field_name='min_date', method='year_filter', label='Filter by year')
    min_date = DateFromToRangeFilter()

    class Meta:
        model = Composite
        fields = ('active', 'interval', 'year', 'min_date', )

    def year_filter(self, queryset, field_name, value):
        return queryset.filter(**{
            'min_date__year': value,
        })


class SentinelTileAggregationLayerFilter(FilterSet):

    year = NumberFilter(field_name='sentineltile', method='year_filter', label='Filter by year')

    class Meta:
        model = SentinelTileAggregationLayer
        fields = ('active', 'aggregationlayer', 'year', )

    def year_filter(self, queryset, field_name, value):
        return queryset.filter(**{
            'sentineltile__collected__year': value,
        })
