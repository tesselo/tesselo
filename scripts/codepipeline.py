import boto3

client = boto3.client('codebuild', region_name='eu-west-1')
# DEVELOP
response = client.update_project(
    name='BuildBackendDevelop',
    environment={
        'type': 'LINUX_CONTAINER',
        'image': 'aws/codebuild/docker:17.09.0',
        'computeType': 'BUILD_GENERAL1_SMALL',
        'environmentVariables': [
            {"name": "AWS_STORAGE_BUCKET_NAME_MEDIA", "value": "tesselo-media-develop", "type": "PLAINTEXT"},
            {"name": "AWS_STORAGE_BUCKET_NAME_STATIC", "value": "dev.static.tesselo.com", "type": "PLAINTEXT"},
            {"name": "AWS_ACCESS_KEY_ID", "value": "", "type": "PLAINTEXT"},
            {"name": "AWS_SECRET_ACCESS_KEY", "value": "", "type": "PLAINTEXT"},
            {"name": "DB_HOST", "value": "tesselo-staging.ce3mi8diupls.eu-west-1.rds.amazonaws.com", "type": "PLAINTEXT"},
            {"name": "DB_USER", "value": "tesselo", "type": "PLAINTEXT"},
            {"name": "DB_NAME", "value": "tesselo_dev", "type": "PLAINTEXT"},
            {"name": "DB_PASSWORD", "value": "", "type": "PLAINTEXT"},
            {"name": "STAGE", "value": "dev", "type": "PLAINTEXT"},
            {"name": "BUCKET", "value": "dev.static.tesselo.com", "type": "PLAINTEXT"}
        ]
    }
)
#STAGING
response = client.update_project(
    name='BuildBackendStaging',
    environment={
        'type': 'LINUX_CONTAINER',
        'image': 'aws/codebuild/docker:17.09.0',
        'computeType': 'BUILD_GENERAL1_SMALL',
        'environmentVariables': [
            {"name": "AWS_STORAGE_BUCKET_NAME_MEDIA", "value": "tesselo-media-staging", "type": "PLAINTEXT"},
            {"name": "AWS_STORAGE_BUCKET_NAME_STATIC", "value": "staging.static.tesselo.com", "type": "PLAINTEXT"},
            {"name": "AWS_ACCESS_KEY_ID", "value": "", "type": "PLAINTEXT"},
            {"name": "AWS_SECRET_ACCESS_KEY", "value": "", "type": "PLAINTEXT"},
            {"name": "DB_HOST", "value": "tesselo-staging.ce3mi8diupls.eu-west-1.rds.amazonaws.com", "type": "PLAINTEXT"},
            {"name": "DB_USER", "value": "tesselo", "type": "PLAINTEXT"},
            {"name": "DB_NAME", "value": "tesselo_staging", "type": "PLAINTEXT"},
            {"name": "DB_PASSWORD", "value": "", "type": "PLAINTEXT"},
            {"name": "STAGE", "value": "staging", "type": "PLAINTEXT"},
            {"name": "BUCKET", "value": "staging.static.tesselo.com", "type": "PLAINTEXT"}
        ]
    }
)
#PRODUCTION
response = client.update_project(
    name='BuildBackendDevelop',
    environment={
        'type': 'LINUX_CONTAINER',
        'image': 'aws/codebuild/docker:17.09.0',
        'computeType': 'BUILD_GENERAL1_SMALL',
        'environmentVariables': [
            {"name": "AWS_STORAGE_BUCKET_NAME_MEDIA", "value": "tesselo-media-production", "type": "PLAINTEXT"},
            {"name": "AWS_STORAGE_BUCKET_NAME_STATIC", "value": "static.tesselo.com", "type": "PLAINTEXT"},
            {"name": "AWS_ACCESS_KEY_ID", "value": "", "type": "PLAINTEXT"},
            {"name": "AWS_SECRET_ACCESS_KEY", "value": "", "type": "PLAINTEXT"},
            {"name": "DB_HOST", "value": "", "type": "PLAINTEXT"},
            {"name": "DB_USER", "value": "tesselo", "type": "PLAINTEXT"},
            {"name": "DB_NAME", "value": "tesselo_production", "type": "PLAINTEXT"},
            {"name": "DB_PASSWORD", "value": "", "type": "PLAINTEXT"},
            {"name": "STAGE", "value": "production", "type": "PLAINTEXT"},
            {"name": "BUCKET", "value": "static.tesselo.com", "type": "PLAINTEXT"}
        ]
    }
)
