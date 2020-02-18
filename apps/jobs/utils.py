from django.contrib.contenttypes.models import ContentType
from jobs.models import BatchJob


def track_job(app, model, pk, job):
    """
    Register jobs in BatchJob table.
    """
    if job is None:
        return
    content_type = ContentType.objects.get(
        app_label=app,
        model=model,
    )
    BatchJob.objects.create(
        content_type=content_type,
        object_id=pk,
        job_id=job['jobID'],
    )
    return job
