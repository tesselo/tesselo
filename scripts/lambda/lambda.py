import rasterio as rio

import mercantile

# export LC_ALL=C.UTF-8
# export LANG=C.UTF-8
# export CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# pip install --pre rasterio[s3]>=1.0a4
# CPL_CURL_VERBOSE=1 rio -vv insp s3://sentinel-s2-l1c/tiles/6/U/UG/2015/11/29/0/B03.jp2

with rasterio.open('s3://landsat-pds/L8/139/045/LC81390452014295LGN00/LC81390452014295LGN00_B1.TIF') as src:
    print(src.profile)
