"""
Django settings for tesselo project.

Generated by 'django-admin startproject' using Django 1.10.4.dev20161220101541.

For more information on this file, see
https://docs.djangoproject.com/en/dev/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/dev/ref/settings/
"""
import glob
import os

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'j7$22brg^e@qpnnwtgw%1l@&=9=2yjbo-ky3ox-m_jgym*8iap'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', False) == 'True'
LOCAL = os.environ.get('LOCAL') == 'True' if 'LOCAL' in os.environ else DEBUG

ALLOWED_HOSTS = ['*']

LOGIN_REDIRECT_URL = '/'

# Forward to ssl if not ssl recieved.
SECURE_SSL_REDIRECT = not DEBUG
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Custom c-library locations.
if os.environ.get('ZAPPA', None):
    BASE_DIR_GDAL = '/var/venv/lib/python3.6/site-packages'
elif DEBUG:
    BASE_DIR_GDAL = '/usr/local/lib/python3.6/site-packages'
else:
    BASE_DIR_GDAL = BASE_DIR
    os.environ['GDAL_DATA'] = os.path.join(BASE_DIR, 'rasterio/gdal_data')

GDAL_LIBRARY_PATH = glob.glob(os.path.join(BASE_DIR_GDAL, 'rasterio/.libs/libgdal-*.so.*'))[0]
GEOS_LIBRARY_PATH = glob.glob(os.path.join(BASE_DIR_GDAL, 'rasterio/.libs/libgeos_c-*.so.*'))[0]

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
    'compressor',
    'django_cleanup',
    'rest_framework',
    'rest_framework.authtoken',
    'crispy_forms',
    'django_filters',
    'guardian',
    'django_extensions',
    'django_celery_results',
    'django_celery_beat',
    'corsheaders',

    'raster',
    'raster_aggregation',

    'raster_api',
    'sentinel',
    'classify',
    'formulary',
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
]

ROOT_URLCONF = 'tesselo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': ['tesselo/templates', ],
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

CORS_ORIGIN_ALLOW_ALL = True

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

# AUTH_PASSWORD_VALIDATORS = [
# {
# 'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
# },
# {
# 'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
# },
# {
# 'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
# },
# {
# 'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
# },
# ]

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
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', None)
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', None)
AWS_S3_URL_PROTOCOL = 'https'

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/dev/howto/static-files/

STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'compressor.finders.CompressorFinder',
)

STATIC_ROOT = '/tmp/staticfiles'
if LOCAL:
    STATIC_URL = '/static/'
else:
    # Storage class for static files and compressor.
    STATICFILES_STORAGE = 'tesselo.s3storages.StaticRootCachedS3Boto3Storage'
    # Get S3 bucket name.
    AWS_STORAGE_BUCKET_NAME_STATIC = os.environ.get('AWS_STORAGE_BUCKET_NAME_STATIC')
    # Set the url to the bucket for serving files.
    if AWS_STORAGE_BUCKET_NAME_STATIC == 'dev.static.tesselo.com':
        STATIC_URL = 'https://devstatic.tesselo.com/'
        AWS_S3_CUSTOM_DOMAIN = 'devstatic.tesselo.com'
    elif AWS_STORAGE_BUCKET_NAME_STATIC == 'staging.static.tesselo.com':
        STATIC_URL = 'https://stagingstatic.tesselo.com/'
        AWS_S3_CUSTOM_DOMAIN = 'stagingstatic.tesselo.com'
    elif AWS_STORAGE_BUCKET_NAME_STATIC == 'static.tesselo.com':
        STATIC_URL = 'https://static.tesselo.com/'
        AWS_S3_CUSTOM_DOMAIN = 'static.tesselo.com'
    # Define the storage class and url for compression.
    COMPRESS_STORAGE = STATICFILES_STORAGE
    COMPRESS_URL = STATIC_URL

# Compressor settings
COMPRESS_JS_FILTERS = [
    'compressor.filters.jsmin.JSMinFilter',
]

COMPRESS_CSS_FILTERS = [
    'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.CSSMinFilter',
]

COMPRESS_PRECOMPILERS = (
    ('text/scss', 'sass {infile} {outfile}'),
    ('text/less', 'less {infile} > {outfile}'),
)

COMPRESS_OFFLINE = True

# Storage settings
if LOCAL:
    MEDIA_ROOT = '/tesselo_media'
else:
    # Storage class for media files
    DEFAULT_FILE_STORAGE = 'tesselo.s3storages.PrivateMediaS3Boto3Storage'
    # Get S3 bucket name
    AWS_STORAGE_BUCKET_NAME_MEDIA = os.environ.get('AWS_STORAGE_BUCKET_NAME_MEDIA')
    # Set the url to the bucket for serving files
    MEDIA_URL = 'https://{bucket}.s3.amazonaws.com/'.format(
        bucket=AWS_STORAGE_BUCKET_NAME_MEDIA,
    )

# Rest framework settings.
REST_FRAMEWORK = {
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'raster_api.authentication.ExpiringTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_FILTER_BACKENDS': ('django_filters.rest_framework.DjangoFilterBackend', ),
}

# Celery settings.
if LOCAL:
    CELERY_BROKER_URL = 'amqp://guest:guest@localhost:5672//'
else:
    CELERY_BROKER_URL = 'redis://tesselo-redis-broker.xu1tb1.0001.euc1.cache.amazonaws.com:6379'
    CELERY_BROKER_TRANSPORT_OPTIONS = {
        'visibility_timeout': 2 * 60 * 60,  # 2 hours.
        'queue_name_prefix': 'tesselo-',
    }
CELERY_RESULT_BACKEND = 'django-db'
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_ACKS_LATE = True

# Django-raster settings
RASTER_USE_CELERY = True
RASTER_PARSE_SINGLE_TASK = True
RASTER_WORKDIR = os.environ.get('RASTER_WORKDIR', None)

# Logger settings.
if not DEBUG:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'verbose': {
                'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
            },
        },
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'verbose'
            }
        },
        'loggers': {
            'django': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': True,
            },
        },
    }
