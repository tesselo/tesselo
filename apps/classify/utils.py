import math

import numpy
from sklearn.base import TransformerMixin
from sklearn.preprocessing import RobustScaler
from sklearn.utils import shuffle
from tensorflow.keras.utils import Sequence


class RNNRobustScaler(TransformerMixin):
    """
    Robust scaler for 3D inputs.
    https://stackoverflow.com/questions/50125844/how-to-standard-scale-a-3d-matrix
    """

    def __init__(self, *args, **kwargs):
        self._scaler = RobustScaler(*args, **kwargs)
        self._orig_features = None
        self._orig_timesteps = None

    def fit(self, X, *args, **kwargs):
        # Save the original shape to reshape the flattened X later
        # back to its original shape
        if len(X.shape) != 3:
            raise ValueError('RNNRobustScaler only works for 3D arrays.')
        self._orig_features = X.shape[2]
        self._orig_timesteps = X.shape[1]
        X = self._flatten(X)
        self._scaler.fit(X, *args, **kwargs)
        return self

    def transform(self, X, *args, **kwargs):
        X = numpy.array(X)
        X = self._flatten(X)
        X = self._scaler.transform(X, *args, **kwargs)
        X = self._reshape(X)
        return X

    def _flatten(self, X):
        X = X.reshape(X.shape[0] * self._orig_timesteps, self._orig_features)
        return X

    def _reshape(self, X):
        # Reshape X back to it's original shape
        n_pixels = int(X.shape[0] / self._orig_timesteps)
        X = X.reshape(n_pixels, self._orig_timesteps, self._orig_features)
        return X


class PixelSequence(Sequence):
    """
    A batch generator for fitting Keras models.
    """
    def __init__(self, x_set, y_set, batch_size, shuffle=True):
        self.x, self.y = x_set, y_set
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.on_epoch_end()

    def __len__(self):
        return math.ceil(len(self.x) / self.batch_size)

    def __getitem__(self, idx):
        batch_x = self.x[idx * self.batch_size:(idx + 1) * self.batch_size]
        batch_y = self.y[idx * self.batch_size:(idx + 1) * self.batch_size]
        return batch_x, batch_y

    def on_epoch_end(self):
        if self.shuffle is True:
            self.x, self.y = shuffle(self.x, self.y)
