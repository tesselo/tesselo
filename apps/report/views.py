from django.db.models.expressions import RawSQL
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from raster_api.permissions import IsReadOnly
from raster_api.views import PermissionsModelViewSet
from report.filters import ReportAggregationFilter
from report.models import ReportAggregation, ReportSchedule
from report.permissions import ReportAggregationPermission
from report.serializers import ReportAggregationSerializer, ReportScheduleSerializer


class ReportScheduleViewSet(PermissionsModelViewSet):
    queryset = ReportSchedule.objects.all().order_by('id')
    serializer_class = ReportScheduleSerializer
    _model = 'reportschedule'


class ReportAggregationPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 150


class ReportAggregationViewSet(ReadOnlyModelViewSet):
    permission_classes = (IsAuthenticated, IsReadOnly, ReportAggregationPermission)
    pagination_class = ReportAggregationPagination
    serializer_class = ReportAggregationSerializer
    filter_backends = [SearchFilter, DjangoFilterBackend]
    filter_class = ReportAggregationFilter
    search_fields = ['aggregationarea__name', ]
    normal_ordering_fields = [
        'stats_avg',
        '-stats_avg',
        'aggregationarea__name',
        '-aggregationarea__name',
        'min_date',
        '-min_date',
    ]
    json_ordering_fields = [
        'value__',
        'value_percentage__',
        '-value__',
        '-value_percentage__',
    ]

    def get_queryset(self):
        # Setup initial queryset.
        qs = ReportAggregation.objects.all()
        # Get ordering query argument.
        ordering = self.request.GET.get('ordering', '').split(',')
        # Match requested ordering with allowed ordering strings.
        normal_orderings = [dat for dat in ordering if dat in self.normal_ordering_fields]
        json_orderings = [dat for dat in ordering if any(dat.startswith(jdat) for jdat in self.json_ordering_fields)]
        # Apply ordering filters.
        if len(json_orderings):
            # Only use first ordering, the others are obsolete on a float field.
            key, val = json_orderings[0].split('__')
            # Instantiate ordering sql.
            order = RawSQL(key.lstrip('-') + "->%s", (val,))
            # Choose asc vs desc order, with nulls first or last.
            if key.startswith('-'):
                order = order.asc(nulls_first=True)
            else:
                order = order.desc(nulls_last=True)
            # Add ordering to queryset.
            qs = qs.order_by(order)
        elif len(normal_orderings):
            qs = qs.order_by(*normal_orderings)
        else:
            qs = qs.order_by('aggregationarea__name', 'min_date')

        return qs
