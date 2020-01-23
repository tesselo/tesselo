from raster.tiles.utils import tile_scale

ZOOM = 14

SCALE = tile_scale(ZOOM)

VALUE_CONFIG_ERROR_MSG = 'Found different values for same category.'
PREDICTION_CONFIG_ERROR_MSG = 'Predicted layer needs to have an aggregationlayer specified.'
TRAINING_DATA_SPLIT_ERROR_MSG = 'Could not split dataset by pixel. Are the training samples overlapping?'
FITTING_ERROR_MSG = 'Failed fitting classifier'
KERAS_JSON_MALFORMED_ERROR_MSG = 'Improper config format. Keras model JSON malformed, could not instantiate model.'
KERAS_MIN_ONE_LAYER_ERROR_MSG = 'Keras model incomplete, at least one layer is required.'
KERAS_LAST_LAYER_NOT_DENSE_ERROR_MSG = 'Keras last layer is expected to be "Dense".'
KERAS_LAST_LAYER_UNITS_ERROR_MSG_TMPL = 'Keras Dense last layer has {} units, but traininlayer has {} categories.'

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
