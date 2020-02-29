from django_filters.rest_framework import DateFilter, FilterSet

from report.models import ReportAggregation


class ReportAggregationFilter(FilterSet):

    date_after = DateFilter(field_name='min_date', lookup_expr='gte')
    date_before = DateFilter(field_name='max_date', lookup_expr='lte')

    class Meta:
        model = ReportAggregation
        fields = (
            'formula', 'aggregationlayer', 'aggregationarea', 'predictedlayer',
            'composite', 'date_after', 'date_before',
        )
