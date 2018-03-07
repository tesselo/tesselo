import copy
import os

import boto3

BATCH_JOB_BASE = {
    'jobQueue': 'tesselo-{stage}',
    'jobDefinition': 'tesselo-{stage}',
    'containerOverrides': {
        'command': ['python', 'manage.py', 'sentinel', ],
        'environment': [
            {'name': 'AWS_ACCESS_KEY_ID', 'value': os.environ.get('AWS_ACCESS_KEY_ID')},
            {'name': 'AWS_SECRET_ACCESS_KEY', 'value': os.environ.get('AWS_SECRET_ACCESS_KEY')},
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


def run_ecs_command(command_input, vcpus=1, memory=1024, retry=1):
    '''
    Execute a command on an ECS instance.
    Execute a command on an ECS instance.
    '''
    if not isinstance(command_input, list):
        raise ValueError('The command_input is required to be a list.')

    # Ensure input is in string format (required for the container overrides).
    command_input = [str(dat) for dat in command_input]

    # Copy base command.
    command = copy.deepcopy(BATCH_JOB_BASE)

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

    command['jobQueue'] = command['jobQueue'].format(stage=stage)
    command['jobDefinition'] = command['jobDefinition'].format(stage=stage)

    # Set retry stragegy.
    command['retryStrategy']['attempts'] = retry

    # Instanciate batch client and submit job.
    client = boto3.client('batch', region_name='us-east-1')
    return client.submit_job(**command)


def sync_sentinel_bucket_utm_zone(utm_zone):
    return run_ecs_command(['sync_sentinel_bucket_utm_zone', utm_zone], memory=512)


def drive_sentinel_bucket_parser():
    return run_ecs_command(['drive_sentinel_bucket_parser', ], memory=512)


def process_l2a(scene_id):
    return run_ecs_command(['process_l2a', scene_id], memory=10000)


def process_compositetile(compositetile_id):
    return run_ecs_command(['process_compositetile', compositetile_id])


def composite_build_callback(compositebuild_id, initiate=False):
    return run_ecs_command(['composite_build_callback', compositebuild_id, initiate])
