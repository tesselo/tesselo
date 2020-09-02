BUCKET_NAME = 'sentinel-s1-l1c'
TILE_INFO_FILE = 'productInfo.json'
TILEINFO_BODY_KEY = 'Body'
INVENTORY_BUCKET_NAME = 'sentinel-inventory'
SENTINEL_1_NODATA_VALUE = 0
SENTINEL_1_ZOOM = 14
SENTINEL_1_DATA_TYPE = 6
DARK_SCENE_EDGE_THRESHOLD = 0.001

# List of band names.
BDVV = 'VV'
BDVH = 'VH'
BDHH = 'HH'
BDHV = 'HV'

# Band choices to be used in models.
BAND_CHOICES = (
    (BDVV, 'VV Polarization'),
    (BDVH, 'VH Polarization'),
    (BDHH, 'HH Polarization'),
    (BDHV, 'HV Polarization'),
)

# Polarization Modes.
POLARIZATION_SV = 'SV'
POLARIZATION_SH = 'DH'
POLARIZATION_DV = 'DV'
POLARIZATION_DH = 'DH'

POLARIZATION_DV_BANDS = [BDVV, BDVH, ]

# Acquisition modes.
ACQUISITON_IW = 'IW'

# Product types.
PRODUCT_TYPE_GRD = 'GRD'

# SNAP Graph processing tool.
GPT_WORKDIR = '/data'
GPT_TERRAIN_CORRECTION_CMD_TEMPLATE = 'gpt /code/apps/sentinel_1/graphs/snap_terrain_correction.xml -Pinput={input} -Poutput={output}'
GPT_DIAG_CONFIG_OUTPUT_CMD = 'gpt --diag'
