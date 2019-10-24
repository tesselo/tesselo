from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
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
    page_size = 1000
    page_size_query_param = 'page_size'
    max_page_size = 5000


class ReportAggregationViewSet(ReadOnlyModelViewSet):
    permission_classes = (IsAuthenticated, IsReadOnly, ReportAggregationPermission)
    pagination_class = ReportAggregationPagination
    queryset = ReportAggregation.objects.all().order_by('id')
    serializer_class = ReportAggregationSerializer
    filter_backends = [SearchFilter, OrderingFilter, DjangoFilterBackend]
    filter_class = ReportAggregationFilter
    search_fields = ['aggregationarea__name', ]
    ordering_fields = ['valuecountresult__stats_avg', 'aggregationarea__name']
    ordering = ['aggregationarea__name']
