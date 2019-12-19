BUCKET_NAME = 'sentinel-s1-l1c'
TILE_INFO_FILE = 'productInfo.json'
TILEINFO_BODY_KEY = 'Body'
INVENTORY_BUCKET_NAME = 'sentinel-inventory'
SENTINEL_1_NODATA_VALUE = 0
SENTINEL_1_ZOOM = 14

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

# SNAP Graph processing tool.
GPT_WORKDIR = '/data'
GPT_TERRAIN_CORRECTION_CMD_TEMPLATE = 'gpt /code/apps/sentinel_1/graphs/snap_terrain_correction.xml -Pinput={input} -Poutput={output}'
