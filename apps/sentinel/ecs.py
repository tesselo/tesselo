import os

import boto3

FARGATE_COMMAND_BASE = {
    'cluster': 'tesselo-workers',
    'taskDefinition': 'tesselo-process-l2a-8GB-2vCPU:1',
    'overrides': {
        'containerOverrides': [
            {
                'name': 'tesselo',
                'command': ['python3.6', 'manage.py', 'sentinel', ],
                "environment": [
                    {"name": "AWS_ACCESS_KEY_ID", "value": os.environ.get("AWS_ACCESS_KEY_ID")},
                    {"name": "AWS_SECRET_ACCESS_KEY", "value": os.environ.get("AWS_SECRET_ACCESS_KEY")},
                    {"name": "AWS_STORAGE_BUCKET_NAME_MEDIA", "value": os.environ.get("AWS_STORAGE_BUCKET_NAME_MEDIA")},
                    {"name": "AWS_STORAGE_BUCKET_NAME_STATIC", "value": os.environ.get("AWS_STORAGE_BUCKET_NAME_STATIC")},
                    {"name": "DB_USER", "value": os.environ.get("DB_USER")},
                    {"name": "DB_PASSWORD", "value": os.environ.get("DB_PASSWORD")},
                    {"name": "DB_HOST", "value": os.environ.get("DB_HOST")},
                    {"name": "DB_NAME", "value": os.environ.get("DB_NAME")},
                ]
            },
        ],
    },
    'launchType': 'FARGATE',
    'networkConfiguration': {
        'awsvpcConfiguration': {
            'subnets': [
                'subnet-4ae19b65',
                'subnet-5007051b',
            ],
            'securityGroups': [
                'sg-66ef6c11',
            ],
            'assignPublicIp': 'ENABLED',
        }
    }
}


def run_ecs_command(command_input):
    """
    Execute a command on an ECS Fargate instance.
    """
    if not isinstance(command_input, list):
        raise ValueError('The command_input is required to be a list.')

    command = FARGATE_COMMAND_BASE.copy()
    command['overrides']['containerOverrides'][0]['command'] += command_input
    client = boto3.client('ecs', region_name='us-east-1')
    return client.run_task(**command)


def sync_sentinel_bucket_utm_zone(utm_zone):
    return run_ecs_command(['sync_sentinel_bucket_utm_zone', utm_zone])


def drive_sentinel_bucket_parser():
    return run_ecs_command(['drive_sentinel_bucket_parser', ])


def process_l2a(scene_id):
    return run_ecs_command(['process_l2a', scene_id])


def process_compositetile(compositetile_id):
    return run_ecs_command(['process_compositetile', compositetile_id])


def composite_build_callback(compositebuild_id, initiate=False):
    return run_ecs_command(['composite_build_callback', compositebuild_id, initiate])
