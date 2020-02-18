from rest_framework.serializers import ModelSerializer, SerializerMethodField

from jobs.models import BatchJob


class BatchJobSerializer(ModelSerializer):

    log = SerializerMethodField()

    class Meta:
        model = BatchJob
        fields = (
            'id', 'job_id', 'status', 'created', 'log_stream_name',
            'description', 'log',
        )

    def get_log(self, obj):
        return obj.get_log()
