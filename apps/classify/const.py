from raster.tiles.utils import tile_scale

ZOOM = 14

SCALE = tile_scale(ZOOM)

VALUE_CONFIG_ERROR_MSG = 'Found different values for same category.'

CHUNK_SIZE = 100

CLASSIFICATION_DATATYPE = 'uint8'
CLASSIFICATION_DATATYPE_GDAL = 1

REGRESSION_DATATYPE = 'float32'
REGRESSION_DATATYPE_GDAL = 6

SENTINEL_PIXELTYPE = 'uint16'
