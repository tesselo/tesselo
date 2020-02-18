from jobs.models import BatchJob
from jobs.serializers import BatchJobSerializer
from raster_api.views import PermissionsModelViewSet


class BatchJobViewSet(PermissionsModelViewSet):

    serializer_class = BatchJobSerializer
    queryset = BatchJob.objects.all()

    _model = 'batchjob'
