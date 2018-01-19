import numpy as np
import rasterio
from rasterio.windows import Window

from osgeo import gdal

tilesize = 256

red = numpy.empty(shape=(1, tilesize, tilesize)).astype(src.profile['dtype'])
src.read(out=red, window=Window(0, 0, 5000, 5000))
print(red)

src.read(window=Window(1024 * 3, 1024 * 2, 1024, 1024))


LC_ALL=C.UTF-8 LANG=C.UTF-8 CPL_CURL_VERBOSE=1 CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt python3


with rasterio.Env(aws_access_key_id='AKIAJVWMVHXVKX7I2A6Q', aws_secret_access_key='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') as env:
   tilesize = 512
   win = Window(0, 0, 10000, 10000)
   stile = 'tiles/29/S/ND/2017/11/16/0'
   src = rasterio.open('s3://sentinel-s2-l1c/{0}/B04.jp2'.format(stile))
   red = numpy.empty(shape=(1, tilesize, tilesize)).astype(src.profile['dtype'])
   src.read(window=win)




gdal.SetConfigOption('AWS_REGION', 'eu-central-1')
gdal.SetConfigOption('AWS_SECRET_ACCESS_KEY', '8ypWK3EYxJ7khBSsVg3ADxIuG1S4kg49My4fJtW0')
gdal.SetConfigOption('AWS_ACCESS_KEY_ID', 'AKIAJVWMVHXVKX7I2A6Q')

export AWS_SECRET_ACCESS_KEY=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
export AWS_ACCESS_KEY_ID=AKIAJVWMVHXVKX7I2A6Q

stile = 'tiles/29/S/ND/2017/11/16/0'
path = '/vsis3/sentinel-s2-l1c/{}/B02.jp2'.format(stile)
ds = gdal.Open(path)

band = ds.GetRasterBand(1)

xoff, yoff, xcount, ycount = (0, 0, 100, 100)
np_array = band.ReadAsArray(xoff, yoff, xcount, ycount)
