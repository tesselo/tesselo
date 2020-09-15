import json

import boto3
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
            self.status = self.UNKNOWN
        else:
            # Get job description of first job result.
            job = desc['jobs'][0]
            # Remove container environment, as it may contain secret keys.
            if 'description' in job and 'container' in job['description'] and 'environment' in job['description']['container']:
                del job['description']['container']['environment']
            # Store description and status.
            self.description = json.dumps(job)
            self.status = job['status']
            # Get log stream name of last attempt (there might be multiple attempts.)
            if len(job['attempts']):
                self.log_stream_name = job['attempts'][0]['container']['logStreamName']
            else:
                self.log_stream_name = ''
        self.save()

    def get_log(self, limit=500):
        if not self.log_stream_name:
            return {'error': 'Log stream name is not specified for this job.'}
        return logs.get_log_events(
            logGroupName=const.LOG_GROUP_NAME,
            logStreamName=self.log_stream_name,
            limit=limit,
        )
