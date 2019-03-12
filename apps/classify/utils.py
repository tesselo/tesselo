import numpy
from sklearn.base import TransformerMixin
from sklearn.preprocessing import RobustScaler


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
