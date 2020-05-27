import os

import boto3

from classify.models import Classifier, TrainingPixels
from django.conf import settings
from django.core.management import call_command
from jobs.utils import track_job


def get_batch_job_base():
    # Get AWS credentials.
    aws_key_id = os.environ.get('AWS_ACCESS_KEY_ID_ZAP', None)
    if not aws_key_id:
        aws_key_id = os.environ.get('AWS_ACCESS_KEY_ID')

    aws_key = os.environ.get('AWS_SECRET_ACCESS_KEY_ZAP', None)
    if not aws_key:
        aws_key = os.environ.get('AWS_SECRET_ACCESS_KEY')

    return {
        'jobName': None,
        'jobQueue': None,
        'jobDefinition': None,
        'containerOverrides': {
            'command': [],
            'environment': [
                {'name': 'AWS_ACCESS_KEY_ID', 'value': aws_key_id},
                {'name': 'AWS_SECRET_ACCESS_KEY', 'value': aws_key},
                {'name': 'AWS_STORAGE_BUCKET_NAME_MEDIA', 'value': os.environ.get('AWS_STORAGE_BUCKET_NAME_MEDIA')},
                {'name': 'AWS_STORAGE_BUCKET_NAME_STATIC', 'value': os.environ.get('AWS_STORAGE_BUCKET_NAME_STATIC')},
                {'name': 'DB_USER', 'value': os.environ.get('DB_USER')},
                {'name': 'DB_PASSWORD', 'value': os.environ.get('DB_PASSWORD')},
                {'name': 'DB_HOST', 'value': os.environ.get('DB_HOST')},
                {'name': 'DB_NAME', 'value': os.environ.get('DB_NAME')},
                {'name': 'ZAPPA', 'value': 'True'},
            ]
        },
        'retryStrategy': {
            'attempts': None
        }
    }


def run_ecs_command(command_input, vcpus=1, memory=1024, retry=3, queue='tesselo-{stage}', job='tesselo-{stage}', depends_on=None):
    '''
    Execute a Batch command.
    '''
    if not isinstance(command_input, (tuple, list)):
        raise ValueError('The command_input is required to be a tuple or a list.')

    # Run locally if in debug mode.
    if settings.LOCAL:
        call_command('jobs', *command_input, verbosity=1)
        return

    # Ensure input is in string format (required for the container overrides).
    command_input = [str(dat) for dat in command_input]

    # Copy base command.
    command = get_batch_job_base()

    # Write command name.
    command['jobName'] = '-'.join(command_input)[:128]

    # Set container overrides.
    command['containerOverrides'].update({
        'command': ['python', 'manage.py', 'jobs', ] + command_input,
        'vcpus': vcpus,
        'memory': memory,
    })

    # Set stage dependent variables.
    dbname = os.environ.get('DB_NAME', '')
    if 'dev' in dbname:
        stage = 'dev'
    elif 'staging' in dbname:
        stage = 'staging'
    else:
        stage = 'production'

    command['jobQueue'] = queue.format(stage=stage)
    command['jobDefinition'] = job.format(stage=stage)

    # Set retry stragegy.
    command['retryStrategy']['attempts'] = retry

    # Set job dependency.
    if depends_on:
        if not isinstance(depends_on, (list, tuple)):
            raise ValueError('The depends_on argument is required to be a list or tuple.')
        command['dependsOn'] = [{'jobId': job_id} for job_id in depends_on]

    # Instanciate batch client and submit job.
    client = boto3.client('batch', region_name='eu-west-1')
    return client.submit_job(**command)


def sync_sentinel_bucket_utm_zone(utm_zone):
    return run_ecs_command(['sync_sentinel_bucket_utm_zone', utm_zone])


def drive_sentinel_bucket_parser():
    return run_ecs_command(['drive_sentinel_bucket_parser', ])


def process_l2a(scene_id):
    job = run_ecs_command(['process_l2a', scene_id], retry=1, vcpus=2, memory=10000, queue='tesselo-{stage}-process-l2a')
    return track_job('sentinel', 'sentineltile', scene_id, job)


def process_compositetile(compositetile_id):
    job = run_ecs_command(['process_compositetile', compositetile_id])
    return track_job('sentinel', 'compositetile', compositetile_id, job)


def clear_sentineltile(sentineltile_id, depends_on=None):
    job = run_ecs_command(['clear_sentineltile', sentineltile_id], retry=1, vcpus=1, memory=512, depends_on=depends_on)
    return track_job('sentinel', 'sentineltile', sentineltile_id, job)


def clear_composite(composite_id, depends_on=None):
    job = run_ecs_command(['clear_composite', composite_id], retry=1, vcpus=1, memory=512, depends_on=depends_on)
    return track_job('sentinel', 'composite', composite_id, job)


def composite_build_callback(compositebuild_id, initiate=False, rebuild=False):
    job = run_ecs_command(['composite_build_callback', compositebuild_id, initiate, rebuild])
    return track_job('sentinel', 'compositebuild', compositebuild_id, job)


def train_sentinel_classifier(classifier_id):
    # Get large instance flag for this chunk.
    # Run ecs command with required instance size.
    if Classifier.objects.get(id=classifier_id).needs_large_instance:
        job = run_ecs_command(['train_sentinel_classifier', classifier_id], retry=1, vcpus=2, memory=int(1024 * 14.5), queue='tesselo-{stage}-process-l2a')
    else:
        job = run_ecs_command(['train_sentinel_classifier', classifier_id], retry=1)
    return track_job('classify', 'classifier', classifier_id, job)


def predict_sentinel_layer(predicted_layer_id):
    job = run_ecs_command(['predict_sentinel_layer', predicted_layer_id])
    return track_job('classify', 'predictedlayer', predicted_layer_id, job)


def predict_sentinel_chunk(chunk_id):
    job = run_ecs_command(['predict_sentinel_chunk', chunk_id], retry=1)
    return track_job('classify', 'predictedlayerchunk', chunk_id, job)


def build_predicted_pyramid(predicted_layer_id):
    job = run_ecs_command(['build_predicted_pyramid', predicted_layer_id])
    return track_job('classify', 'predictedlayer', predicted_layer_id, job)


def ingest_naip_manifest():
    return run_ecs_command(['ingest_naip_manifest'], retry=1)


def push_scheduled_composite_builds():
    return run_ecs_command(['push_scheduled_composite_builds'], retry=1)


def populate_report(aggregationlayer_id, composite_id, formula_id, predictedlayer_id):
    return run_ecs_command(['populate_report', aggregationlayer_id, composite_id, formula_id, predictedlayer_id])


def parse_aggregationlayer(pk):
    job = run_ecs_command(['parse_aggregationlayer', pk])
    return track_job('raster_aggregation', 'aggregationlayer', pk, job)


def parse_s3_sentinel_1_inventory():
    return run_ecs_command(['parse_s3_sentinel_1_inventory'], retry=1)


def snap_terrain_correction(sentinel1tile_id):
    job = run_ecs_command(
        ['snap_terrain_correction', sentinel1tile_id],
        vcpus=4,
        memory=1024 * 20,
        retry=1,
        queue='tesselo-{stage}-snap',
        job='tesselo-{stage}-snap',
    )
    return track_job('sentinel_1', 'sentinel1tile', sentinel1tile_id, job)


def populate_trainingpixels(trainingpixels_id):
    job = run_ecs_command(['populate_trainingpixels', trainingpixels_id])
    return track_job('classify', 'trainingpixels', trainingpixels_id, job)


def populate_trainingpixels_patch(trainingpixels_patch_id):
    job = run_ecs_command(['populate_trainingpixels_patch', trainingpixels_patch_id])
    return track_job('classify', 'trainingpixelspatch', trainingpixels_patch_id, job)


def combine_trainingpixels_patches(trainingpixels_id):
    if TrainingPixels.objects.get(id=trainingpixels_id).needs_large_instance:
        job = run_ecs_command(['combine_trainingpixels_patches', trainingpixels_id], retry=1, vcpus=2, memory=int(1024 * 14.5), queue='tesselo-{stage}-process-l2a')
    else:
        job = run_ecs_command(['combine_trainingpixels_patches', trainingpixels_id], retry=1)
    return track_job('classify', 'classifier', trainingpixels_id, job)
