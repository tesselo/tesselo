"""
Django settings for tesselo project.

Generated by 'django-admin startproject' using Django 1.10.4.dev20161220101541.

For more information on this file, see
https://docs.djangoproject.com/en/dev/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/dev/ref/settings/
"""
import glob
import logging
import os
import sysconfig

import sentry_sdk
import structlog
from sentry_sdk.integrations.django import DjangoIntegration
from structlog_sentry import SentryJsonProcessor

sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN", ""),
    integrations=[DjangoIntegration()],
    # Set traces_sample_rate to 0.1 to capture 10%
    traces_sample_rate=0.1,
    # Associate django users to errors
    send_default_pii=True,
)

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'j7$22brg^e@qpnnwtgw%1l@&=9=2yjbo-ky3ox-m_jgym*8iap'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', False) == 'True'

# The local flag is used to run remote commands locally. This is for development
# environments and testing.
LOCAL = os.environ.get('LOCAL', False) == 'True' or DEBUG

ALLOWED_HOSTS = ['*']

LOGIN_REDIRECT_URL = '/'

# Forward to ssl if not ssl recieved.
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

PYTHON_VERSION = sysconfig.get_python_version()

if os.environ.get('ZAPPA', None):
    BASE_DIR_GDAL = f'/var/venv/lib/{PYTHON_VERSION}/site-packages'
elif os.environ.get('TESSELO_GPU', None):
    BASE_DIR_GDAL = f'/usr/local/lib/{PYTHON_VERSION}/site-packages'
else:
    BASE_DIR_GDAL = BASE_DIR

GDAL_LIBRARY_PATH = glob.glob(os.path.join(BASE_DIR_GDAL, 'rasterio.libs/libgdal-*.so.*'))[0]
GEOS_LIBRARY_PATH = glob.glob(os.path.join(BASE_DIR_GDAL, 'rasterio.libs/libgeos_c-*.so.*'))[0]
os.environ['GDAL_DATA'] = os.path.join(BASE_DIR_GDAL, 'rasterio/gdal_data')  # Set gdal data env var.

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',
    'django.contrib.gis',

    'storages',
    'django_cleanup',
    'rest_framework',
    'rest_framework.authtoken',
    'crispy_forms',
    'django_filters',
    'guardian',
    'django_extensions',
    'corsheaders',

    'raster',
    'raster_aggregation',

    'raster_api',
    'sentinel',
    'sentinel_1',
    'classify',
    'formulary',
    'naip',
    'wmts',
    'userinterface',
    'report',
    'jobs',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_structlog.middlewares.RequestMiddleware',
]

ROOT_URLCONF = 'tesselo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['tesselo/templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.static',
            ],
        },
    },
]
# In debug mode, add context processor with debug flag.
if DEBUG:
    TEMPLATES[0]['OPTIONS']['context_processors'].append('tesselo.utils.debug_tag')

WSGI_APPLICATION = 'tesselo.wsgi.application'

# CORS Settings
CORS_ORIGIN_WHITELIST = [
    "https://app.tesselo.com",
    "https://stagingapp.tesselo.com",
    "https://devapp.tesselo.com",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
CORS_ALLOW_CREDENTIALS = True

# Database
# https://docs.djangoproject.com/en/dev/ref/settings/#databases
DATABASES = {
    'default': {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': os.environ.get('DB_NAME', 'tesselo'),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'USER': os.environ.get('DB_USER', 'postgres'),
        'PORT': os.environ.get('DB_PORT', 5432),
        'PASSWORD': os.environ.get('DB_PASSWORD', None),
    }
}


# Password validation
# https://docs.djangoproject.com/en/dev/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)
# Internationalization
# https://docs.djangoproject.com/en/dev/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = os.environ.get('USE_TZ', 'True') == 'True'

# Cache settings.
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
        'LOCATION': '/var/tmp/django_cache',
    }
}

# AWS and S3 Settings
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID_ZAP', None)
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY_ZAP', None)
AWS_S3_URL_PROTOCOL = 'https'
AWS_DEFAULT_ACL = None  # Use bucket default acl.

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/dev/howto/static-files/

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'django.contrib.staticfiles.finders.FileSystemFinder',
)

STATICFILES_DIRS = []

# Set static root.
STATIC_ROOT = '/tmp/staticfiles'
if 'AWS_STORAGE_BUCKET_NAME_STATIC' in os.environ:
    # Get S3 bucket name.
    AWS_STORAGE_BUCKET_NAME_STATIC = os.environ.get('AWS_STORAGE_BUCKET_NAME_STATIC')
    # Storage class for static files.
    STATICFILES_STORAGE = 'tesselo.s3storages.StaticRootS3Boto3Storage'
    # Set the url to the bucket for serving files.
    if AWS_STORAGE_BUCKET_NAME_STATIC == 'dev.static.tesselo.com':
        STATIC_URL = 'https://devstatic.tesselo.com/'
        AWS_S3_CUSTOM_DOMAIN_STATIC = 'devstatic.tesselo.com'
    elif AWS_STORAGE_BUCKET_NAME_STATIC == 'staging.static.tesselo.com':
        STATIC_URL = 'https://stagingstatic.tesselo.com/'
        AWS_S3_CUSTOM_DOMAIN_STATIC = 'stagingstatic.tesselo.com'
    elif AWS_STORAGE_BUCKET_NAME_STATIC == 'static.tesselo.com':
        STATIC_URL = 'https://static.tesselo.com/'
        AWS_S3_CUSTOM_DOMAIN_STATIC = 'static.tesselo.com'
else:
    STATIC_URL = '/static/'

# Storage settings.
if 'AWS_STORAGE_BUCKET_NAME_MEDIA' in os.environ:
    AWS_STORAGE_BUCKET_NAME_MEDIA = os.environ.get('AWS_STORAGE_BUCKET_NAME_MEDIA')
    # Storage class for media files
    DEFAULT_FILE_STORAGE = 'tesselo.s3storages.PrivateMediaS3Boto3Storage'
    # Get S3 bucket name
    # Set the url to the bucket for serving files
    MEDIA_URL = 'https://{bucket}.s3.amazonaws.com/'.format(
        bucket=AWS_STORAGE_BUCKET_NAME_MEDIA,
    )
else:
    MEDIA_ROOT = '/tesselo_media'

# Rest framework settings.
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
        'raster_api.permissions.IsReadOnly',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'raster_api.authentication.CookieTokenAuthentication',
        'raster_api.authentication.QueryKeyAuthentication',
        'raster_api.authentication.ExpiringTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend', ),
}


# Celery settings.
CELERY_BROKER_URL = 'amqp://guest:guest@localhost:5672//'
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_ALWAYS_EAGER = True

# Django-raster settings
RASTER_USE_CELERY = True
RASTER_PARSE_SINGLE_TASK = True
RASTER_WORKDIR = os.environ.get('RASTER_WORKDIR', None)

# Email settings.
DEFAULT_FROM_EMAIL = 'no-reply@tesselo.com'
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    EMAIL_HOST = 'smtp.fastmail.com'
    EMAIL_PORT = '587'
    EMAIL_HOST_USER = 'daniel@tesselo.com'
    EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = True

# Logger settings.
if not DEBUG:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            "json_formatter": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processor": structlog.processors.JSONRenderer(),
            },
        },
        'handlers': {
            'console': {
                'level': 'WARNING',
                'class': 'logging.StreamHandler',
                'formatter': 'json_formatter'
            }
        },
        'loggers': {
            'django_structlog': {
                'handlers': ['console'],
                'level': os.getenv('DJANGO_LOG_LEVEL', 'WARNING'),
                'propagate': True,
            },
        },
    }

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        SentryJsonProcessor(level=logging.ERROR, tag_keys="__all__"),
        structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
    ],
    context_class=structlog.threadlocal.wrap_dict(dict),
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)
