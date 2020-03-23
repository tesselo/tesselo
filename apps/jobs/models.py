import json

import boto3
from botocore.exceptions import NoCredentialsError

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models
from jobs import const

batch = boto3.client('batch', region_name=const.REGION_NAME)
logs = boto3.client('logs', region_name=const.REGION_NAME)


class BatchJob(models.Model):
    UNKNOWN = 'UNKNOWN'
    SUBMITTED = 'SUBMITTED'
    PENDING = 'PENDING'
    RUNNABLE = 'RUNNABLE'
    STARTING = 'STARTING'
    RUNNING = 'RUNNING'
    SUCCEEDED = 'SUCCEEDED'
    FAILED = 'FAILED'
    STATUS_CHOICES = (
        (SUBMITTED, SUBMITTED),
        (PENDING, PENDING),
        (RUNNABLE, RUNNABLE),
        (STARTING, STARTING),
        (RUNNING, RUNNING),
        (SUCCEEDED, SUCCEEDED),
        (FAILED, FAILED),
    )

    created = models.DateTimeField(auto_now=True)
    job_id = models.CharField(max_length=500)
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default=SUBMITTED)

    description = models.TextField()
    log_stream_name = models.CharField(max_length=1500)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    def __str__(self):
        return '{} | {}'.format(self.job_id, self.status)

    def update(self):
        desc = batch.describe_jobs(jobs=[self.job_id])
        if not len(desc['jobs']):
            self.description = ''
            self.status = self.UNKNOWN
            self.log_stream_name = ''
        else:
            job = desc['jobs'][0]
            self.description = json.dumps(job)
            self.status = job['status']
            if len(job['attempts']):
                self.log_stream_name = job['attempts'][0]['container']['logStreamName']
            else:
                self.log_stream_name = ''
        self.save()

    def get_log(self, limit=500):
        try:
            return logs.get_log_events(
                logGroupName=const.LOG_GROUP_NAME,
                logStreamName=self.log_stream_name,
                limit=limit,
            )
        except NoCredentialsError:
            return ''
