from botocore.exceptions import NoCredentialsError
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
        try:
            job.update()
            msg = {'success': 'Updated batch job. New status is "{}".'.format(job.status)}
        except NoCredentialsError:
            msg = {'error': 'Could not retrieve job details - no credentials found.'}
        # Send response.
        return Response(msg)

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated, IsReadOnly, ChangePermissionObjectPermission])
    def log(self, request, pk):
        """
        Retrieve cloudwatch job log.
        """
        # Get batch job object.
        job = self.get_object()
        # Get batch job log.
        try:
            log = job.get_log()
        except NoCredentialsError:
            log = {'error': 'Could not retrieve job log - no credentials found.'}
        # Send response.
        return Response(log)
