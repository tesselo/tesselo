import math

import numpy
from sklearn.base import TransformerMixin
from sklearn.preprocessing import RobustScaler
from sklearn.utils import shuffle
from tensorflow.keras.callbacks import Callback
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
    def __init__(self, x_set, y_set=None, batch_size=32, shuffle=True, sample_weights=None):
        self.x = x_set
        self.y = y_set
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.sample_weights = sample_weights
        self.on_epoch_end()

    def __len__(self):
        return math.ceil(len(self.x) / self.batch_size)

    def __getitem__(self, idx):
        start = idx * self.batch_size
        end = start + self.batch_size

        batch_x = self.x[start:end]
        batch_y = self.y[start:end] if self.y is not None else None
        sample_weights = self.sample_weights[start:end] if self.sample_weights is not None else None

        if batch_y is None and sample_weights is None:
            return batch_x
        elif sample_weights is None:
            return batch_x, batch_y
        else:
            return batch_x, batch_y, sample_weights

    def on_epoch_end(self):
        if self.shuffle is True and self.y is not None:
            if self.sample_weights is None:
                self.x, self.y = shuffle(self.x, self.y)
            else:
                self.x, self.y, self.sample_weights = shuffle(self.x, self.y, self.sample_weights)


class LogCallback(Callback):

    def __init__(self, classifier, epochs):
        super().__init__()
        self.classifier = classifier
        self.epochs = epochs

    def on_epoch_end(self, epoch, logs):
        # Construct log message.
        msg = 'epoch: {}/{}'.format(epoch + 1, self.epochs)
        for key, val in logs.items():
            if val > 10:
                tmpl = ' - {}: {}'
            else:
                tmpl = ' - {}: {:.4f}'
            msg += tmpl.format(key, val)
        self.classifier.write(msg)
