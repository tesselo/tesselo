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

TP_MSG_NON_KERAS = 'Trainingpixel data source is only valid for Keras models found non-keras algorithm instead.'
TP_MSG_REGRESSOR = 'Trainingpixel data source is only valid for discrete models, found regressor algorithm instead.'
TP_MSG_NOT_FINISHED = 'Found an unpopulated trainingpixels object, populate trainingpixels object before training.'

SIEVE_CONIFG_ERROR_MSG = 'Sieving is only allowed on discrete classifications. Found regressor type.'

CLASSIFICATION_DATATYPE = 'uint8'
CLASSIFICATION_DATATYPE_GDAL = 1
CLASSIFICATION_NODATA = 0

REGRESSION_DATATYPE = 'float32'
REGRESSION_DATATYPE_GDAL = 6

SENTINEL_PIXELTYPE = 'uint16'

PIPELINE_ESTIMATOR_NAME = 'estimator'
PIPELINE_SCALER_NAME = 'scaler'

ZIP_ESTIMATOR_NAME = 'estimator.hdf5'
ZIP_PIPELINE_NAME = 'pipeline.pickle'

KERAS_FIT_ARGS = [
    'batch_size',
    'epochs',
    'verbose',
    'callbacks',
    'validation_split',
    'validation_data',
    'shuffle',
    'class_weight',
    'sample_weight',
    'initial_epoch',
    'steps_per_epoch',
    'validation_steps',
    'validation_batch_size',
    'validation_freq',
    'max_queue_size',
    'workers',
    'use_multiprocessing',
]

KERAS_TRAIN_TYPE = 'float16'
