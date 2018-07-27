import os

import boto3

from django.conf import settings
from django.core.management import call_command


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
        'jobDefinition': 'tesselo-{stage}',
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


def run_ecs_command(command_input, vcpus=1, memory=1024, retry=3, queue='tesselo-{stage}'):
    '''
    Execute a Batch command.
    '''
    if not isinstance(command_input, (tuple, list)):
        raise ValueError('The command_input is required to be a tuple or a list.')

    # Run locally if in debug mode.
    if settings.LOCAL:
        call_command('sentinel', *command_input, verbosity=1)
        return

    # Ensure input is in string format (required for the container overrides).
    command_input = [str(dat) for dat in command_input]

    # Copy base command.
    command = get_batch_job_base()

    # Write command name.
    command['jobName'] = '-'.join(command_input)[:128]

    # Set container overrides.
    command['containerOverrides'].update({
        'command': ['python', 'manage.py', 'sentinel', ] + command_input,
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
    command['jobDefinition'] = command['jobDefinition'].format(stage=stage)

    # Set retry stragegy.
    command['retryStrategy']['attempts'] = retry

    # Instanciate batch client and submit job.
    client = boto3.client('batch', region_name='eu-west-1')
    return client.submit_job(**command)


def sync_sentinel_bucket_utm_zone(utm_zone):
    return run_ecs_command(['sync_sentinel_bucket_utm_zone', utm_zone])


def drive_sentinel_bucket_parser():
    return run_ecs_command(['drive_sentinel_bucket_parser', ])


def process_l2a(scene_id):
    return run_ecs_command(['process_l2a', scene_id], vcpus=2, memory=10000, queue='tesselo-{stage}-process-l2a')


def process_compositetile(compositetile_id):
    return run_ecs_command(['process_compositetile', compositetile_id])


def composite_build_callback(compositebuild_id, initiate=False, rebuild=False):
    return run_ecs_command(['composite_build_callback', compositebuild_id, initiate, rebuild])


def train_sentinel_classifier(classifier_id):
    return run_ecs_command(['train_sentinel_classifier', classifier_id], vcpus=2, memory=10000, queue='tesselo-{stage}-process-l2a')


def predict_sentinel_layer(predicted_layer_id):
    return run_ecs_command(['predict_sentinel_layer', predicted_layer_id])


def predict_sentinel_chunk(predicted_layer_id, from_idx, to_idx):
    return run_ecs_command(['predict_sentinel_chunk', predicted_layer_id, from_idx, to_idx])


def build_predicted_pyramid(predicted_layer_id):
    return run_ecs_command(['build_predicted_pyramid', predicted_layer_id])
