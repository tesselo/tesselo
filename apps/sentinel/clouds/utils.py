import ephem
import numpy

from sentinel import const


def sun(time, lat, lon):
    """
    Computes average sun angle for a given tile.
    """
    # Create the observer.
    obs = ephem.Observer()
    obs.date = time
    obs.lat = lat
    obs.lon = lon
    # Get the sun.
    sun = ephem.Sun()
    # Compute observation angle.
    sun.compute(obs)
    # Return result as degrees.
    return ephem.degrees(sun.alt), ephem.degrees(sun.az)


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
