from raster.tiles.utils import tile_scale

ZOOM = 14

SCALE = tile_scale(ZOOM)

VALUE_CONFIG_ERROR_MSG = 'Found different values for same category.'
PREDICTION_CONFIG_ERROR_MSG = 'Predicted layer needs to have an aggregationlayer specified.'

CHUNK_SIZE = 100

CLASSIFICATION_DATATYPE = 'uint8'
CLASSIFICATION_DATATYPE_GDAL = 1

REGRESSION_DATATYPE = 'float32'
REGRESSION_DATATYPE_GDAL = 6

SENTINEL_PIXELTYPE = 'uint16'

PIPELINE_ESTIMATOR_NAME = 'estimator'
PIPELINE_SCALER_NAME = 'scaler'

ZIP_ESTIMATOR_NAME = 'estimator.hdf5'
ZIP_PIPELINE_NAME = 'pipeline.pickle'
