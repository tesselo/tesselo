import json

from rest_framework.serializers import ModelSerializer, SerializerMethodField

from jobs.models import BatchJob


class BatchJobSerializer(ModelSerializer):

    log = SerializerMethodField()
    description = SerializerMethodField()

    class Meta:
        model = BatchJob
        fields = (
            'id', 'job_id', 'status', 'created', 'log_stream_name',
            'description', 'log',
        )

    def get_description(self, obj):
        try:
            desc = json.loads(obj.description)
        except json.decoder.JSONDecodeError:
            desc = 'Could not get description. JSON decode error.'
        return desc

    def get_log(self, obj):
        return obj.get_log()
