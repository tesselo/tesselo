from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from jobs.models import BatchJob
from jobs.serializers import BatchJobSerializer
from raster_api.permissions import ChangePermissionObjectPermission
from raster_api.views import IsReadOnly, PermissionsModelViewSet


class BatchJobViewSet(PermissionsModelViewSet):

    serializer_class = BatchJobSerializer
    queryset = BatchJob.objects.all()

    _model = 'batchjob'

    @action(detail=True, methods=['get', 'post'], permission_classes=[IsAuthenticated, IsReadOnly, ChangePermissionObjectPermission])
    def refresh(self, request, pk):
        """
        Update batch job status.
        """
        # Get batch job object.
        job = self.get_object()
        # Update status
        job.update()

        return Response({
            'success': 'Updated batch job. New status is "{}".'.format(job.status),
        })
