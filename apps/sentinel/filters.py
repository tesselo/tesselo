from django_filters.rest_framework import BooleanFilter, CharFilter, DateFilter, FilterSet, NumberFilter

from sentinel.models import SentinelTile


class SentinelTileFilter(FilterSet):

    max_clouds = NumberFilter(field_name='cloudy_pixel_percentage', lookup_expr='lte')
    min_data_coverage = NumberFilter(field_name='data_coverage_percentage', lookup_expr='gte')

    collected_after = DateFilter(field_name='collected', lookup_expr='gte')
    collected_before = DateFilter(field_name='collected', lookup_expr='lte')

    coords = CharFilter(field_name='tile_data_geom', method='coords_filter')

    populated_only = BooleanFilter(field_name='sentineltileband', method='populated_only_filter', label='Populated only')

    class Meta:
        model = SentinelTile
        fields = ['max_clouds', 'min_data_coverage', 'collected_after', 'collected_before', 'populated_only', ]

    def coords_filter(self, queryset, name, value):
        return queryset.filter(**{
            name + '__intersects': 'SRID=3857;POINT({} {})'.format(*value.split(',')),
        })

    def populated_only_filter(self, queryset, name, value):
        if value:
            queryset = queryset.exclude(**{
                name: None,
            })
        return queryset
