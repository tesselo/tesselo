from django_filters.rest_framework import FilterSet, NumberFilter

from sentinel.models import Composite


class CompositeFilter(FilterSet):

    year = NumberFilter(name='min_date', method='year_filter', label='Filter by year')

    class Meta:
        model = Composite
        fields = ('active', 'official', 'interval', 'year', )

    def year_filter(self, queryset, name, value):
        return queryset.filter(**{
            'min_date__year': value,
        })
