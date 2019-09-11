from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ReadOnlyModelViewSet

from raster_api.permissions import IsReadOnly
from raster_api.views import PermissionsModelViewSet
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
    filter_fields = (
        'formula', 'aggregationlayer', 'aggregationarea', 'predictedlayer',
        'composite',
    )
