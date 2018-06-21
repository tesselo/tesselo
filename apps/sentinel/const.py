import datetime

import numpy
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE

# Set parameters for bucket praser
CLIENT_TYPE = 's3'
BUCKET_NAME = 'sentinel-s2-l1c'
PAGINATOR_LOOKUP = 'list_objects'
PAGINATOR_BASE_PREFIX = 'tiles/'
TILE_INFO_FILE = 'tileInfo.json'
TILE_INFO_FILE_JMES_SEARCH = "Contents[?contains(Key, '/{0}') == `true`].Key".format(TILE_INFO_FILE)
TILEINFO_BODY_KEY = 'Body'

# Fix zoom levels for the different sentinel resolutions.
ZOOM_LEVEL_10M = 14
ZOOM_LEVEL_20M = 13
ZOOM_LEVEL_60M = 11
ZOOM_LEVEL_WORLDLAYER = 10

# Multipliers to move from one zoom level to another
M12 = 2 ** (ZOOM_LEVEL_10M - ZOOM_LEVEL_20M)
M16 = 2 ** (ZOOM_LEVEL_10M - ZOOM_LEVEL_60M)
M26 = 2 ** (ZOOM_LEVEL_20M - ZOOM_LEVEL_60M)

# Set parameters for queue driver
MIN_TASK_QUEUE_LENGTH = 50
SENTINEL_NODATA_VALUE = 0
QUANTIFICATION_VALUE = 10000
MAX_CLOUD_COHORT = 30
MIN_PIXEL_COVERAGE = 20
MAX_SCENES_PER_MGRSTILE = 4

# Set parameters for models
BUCKET_URL = 'http://{0}.s3.amazonaws.com/'.format(BUCKET_NAME)

GRANULE_FILE_EXTENSION = '.jp2'
NR_OF_BANDS = 13
NUMBER_OF_UTM_ZONES = 60

TILESCALE_10M = 5378777689100435.0 / 562949953421312.0

RESULT_DICT = {
    'driver': 'tif',
    'compress': 'DEFLATE',
    'width': WEB_MERCATOR_TILESIZE,
    'height': WEB_MERCATOR_TILESIZE,
    'scale': [TILESCALE_10M, -TILESCALE_10M],
    'srid': WEB_MERCATOR_SRID,
    'datatype': 2,
    'bands': [{'nodata_value': SENTINEL_NODATA_VALUE, }, ],
}

# Cloud Extraction Indices, these are range indices for 2d arrays that are
# needed to extract values by index when doing the cloud removal.
CLOUD_IDX1, CLOUD_IDX2 = numpy.indices((WEB_MERCATOR_TILESIZE, WEB_MERCATOR_TILESIZE))

AGG_FACTOR = 2
AGG_TILE_SIZE = WEB_MERCATOR_TILESIZE // AGG_FACTOR
AGG_TILE_SIZE_SQ = AGG_TILE_SIZE ** 2

# List of band names.
BD1 = 'B01.jp2'
BD2 = 'B02.jp2'
BD3 = 'B03.jp2'
BD4 = 'B04.jp2'
BD5 = 'B05.jp2'
BD6 = 'B06.jp2'
BD7 = 'B07.jp2'
BD8 = 'B08.jp2'
BD8A = 'B8A.jp2'
BD9 = 'B09.jp2'
BD10 = 'B10.jp2'
BD11 = 'B11.jp2'
BD12 = 'B12.jp2'
SCL = 'SCL.jp2'

# Band choices to be used in models.
BAND_CHOICES = (
    (BD1, 'Band 1 - Coastal aerosol, WL 0.443 mu, RES 60 m'),
    (BD2, 'Band 2 - Blue, WL 0.490 mu, RES 10 m'),
    (BD3, 'Band 3 - Green, WL 0.560 mu, RES 10 m'),
    (BD4, 'Band 4 - Red WL 0.665 mu, RES 10m'),
    (BD5, 'Band 5 - Vegetation Red Edge, WL 0.705, RES 20 m'),
    (BD6, 'Band 6 - Vegetation Red Edge, WL 0.740, RES 20 m'),
    (BD7, 'Band 7 - Vegetation Red Edge, WL 0.783, RES 20 m'),
    (BD8, 'Band 8 - NIR, WL 0.842, RES 10 m'),
    (BD8A, 'Band 8A - Vegetation Red Edge, WL 0.865, RES 20 m'),
    (BD9, 'Band 9 - Water vapour, WL 0.945, RES 60 m'),
    (BD10, 'Band 10 - SWIR - Cirrus, WL 1.375, RES 60 m'),
    (BD11, 'Band 11 - SWIR, WL 1.610, RES 20 m'),
    (BD12, 'Band 12 - SWIR, WL 2.190, RES 20 m'),
)

# Official resolution of each band.
BAND_RESOLUTIONS = {
    BD1: 60,
    BD2: 10,
    BD3: 10,
    BD4: 10,
    BD5: 20,
    BD6: 20,
    BD7: 20,
    BD8: 10,
    BD8A: 20,
    BD9: 60,
    BD10: 60,
    BD11: 20,
    BD12: 20,
}

# List of bands by resolution.
BANDS_10M = [BD2, BD3, BD4, BD8, ]
BANDS_20M = [BD5, BD6, BD7, BD8A, BD11, BD12, ]
BANDS_60M = [BD1, BD9, BD10, ]

BANDS_COUNT_BY_RES = {
    ZOOM_LEVEL_10M: len(BANDS_10M),
    ZOOM_LEVEL_20M: len(BANDS_20M),
    ZOOM_LEVEL_60M: len(BANDS_60M),
}

# L2A bucket.
L2A_BUCKET = 's3://sentinel-s2-l2a/'
L2A_AVAILABILITY_DATE = datetime.date(2017, 3, 28)

# Sentinel2 Process levels.
LEVEL_L1C = 'l1c'
LEVEL_L2A = 'l2a'

PROCESS_LEVELS = (
    (LEVEL_L1C, 'Level 1C'),
    (LEVEL_L2A, 'Level 2A'),
)

# Sen2Cor Scene Classification parameters.
SCENE_CLASS_LEGEND = {
    0: 'NO_DATA',
    1: 'SATURATED_OR_DEFECTIVE',
    2: 'DARK_AREA_PIXELS',
    3: 'CLOUD_SHADOWS',
    4: 'VEGETATION',
    5: 'NOT_VEGETATED',
    6: 'WATER',
    7: 'UNCLASSIFIED',
    8: 'CLOUD_MEDIUM_PROBABILITY',
    9: 'CLOUD_HIGH_PROBABILITY',
    10: 'THIN_CIRRUS',
    11: 'SNOW',
}

SCENE_CLASS_EXCLUDE = (0, 1, 3, 8, 9, 10)
SCENE_CLASS_DEPREORITIZE = (2, 7, 11)
SCENE_CLASS_KEEP = (4, 5, 6)

EXCLUDE_VALUE = 99
