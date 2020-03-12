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
    max_page_size = 50


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
    ]

    def get_queryset(self):
        qs = ReportAggregation.objects.all()
        ordering = self.request.GET.get('ordering', '')
        if ordering in self.normal_ordering_fields or any(dat in ordering for dat in self.json_ordering_fields):
            qs = qs.order_by(ordering)
        else:
            qs = qs.order_by('aggregationarea__name', 'min_date')
        return qs
