from __future__ import unicode_literals

import ephem


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
