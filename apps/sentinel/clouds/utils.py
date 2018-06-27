import datetime

import ephem
import numpy

from sentinel import const


def sun(time, lat, lon):
    """
    Computes average sun angle for a given tile.
    """
    # Check input types.
    if not isinstance(lat, (float, int)):
        raise ValueError('Latitude needs to be float or integer.')
    if not isinstance(lon, (float, int)):
        raise ValueError('Longitude needs to be float or integer.')
    if not isinstance(time, datetime.datetime):
        raise ValueError('Time input needs to be a datetime instance.')
    # Create the observer. The arguments here need to be in str format,
    # otherwise the results are scrambled. Ephem is very sensitive to input
    # types apparently.
    obs = ephem.Observer()
    obs.date = time.strftime('%y-%m-%d %H:%M:%S')
    obs.lat = str(lat)
    obs.lon = str(lon)
    # Get the sun.
    sun = ephem.Sun()
    # Compute observation angle.
    sun.compute(obs)
    # Return result as degrees.
    return float(sun.alt), float(sun.az)


def nodata_mask(stack):
    """
    Compute mask that indicates nodata pixels over all bands. This mask can be
    used to avoid selecting nodata pixels in composites.
    """
    return numpy.any([
        stack[const.BD2] == const.SENTINEL_NODATA_VALUE,  # 10m
        stack[const.BD12] == const.SENTINEL_NODATA_VALUE,  # 20m
        stack[const.BD1] == const.SENTINEL_NODATA_VALUE,  # 60m
    ], axis=0)


def scale_array(arr, vmin, vmax):
    arr = numpy.clip(arr, vmin, vmax)
    return (arr - vmin) / (vmax - vmin)
