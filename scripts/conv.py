import os
import pickle
from collections import OrderedDict

import numpy as np

import matplotlib.pyplot as plt
import statsmodels
import tesselate
from django.contrib.gis.gdal import GDALRaster
from scipy import misc, signal

os.chdir('/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports')

regions = pickle.load(open('regions.pickle', 'rb'))

region_key = 'evora'
#region_key = 'castelo-branco'

print('Opening data for', region_key)
tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')
tess.type_dict = OrderedDict([('eu', 3), ('euy', 2), ('pi', 4), ('sob', 5)])

# Get targets from disk.
targets = tess.read_target_rasters_from_disk(region_key)

ascent_b = targets['B02.jp2'].bands[0].data().astype('float')
ascent_g = targets['B03.jp2'].bands[0].data().astype('float')
ascent_r = targets['B04.jp2'].bands[0].data().astype('float')

ascent_b *= 255 / np.max(ascent_b)
ascent_g *= 255 / np.max(ascent_g)
ascent_r *= 255 / np.max(ascent_r)

ascent = 0.2126 * ascent_r + 0.7152 * ascent_g + 0.0722 * ascent_b

#ascent = misc.ascent()
scharr = np.array([[ -3-3j, 0-10j,  +3 -3j],
                   [-10+0j, 0+ 0j, +10 +0j],
                   [ -3+3j, 0+10j,  +3 +3j]]) # Gx + j*Gy
grad = signal.convolve2d(ascent, scharr, boundary='symm', mode='same')


fig, (ax_orig, ax_mag, ax_ang) = plt.subplots(3, 1, figsize=(6, 15))
ax_orig.imshow(ascent, cmap='gray')
ax_orig.set_title('Original')
ax_orig.set_axis_off()
ax_mag.imshow(np.absolute(grad), cmap='gray')
ax_mag.set_title('Gradient magnitude')
ax_mag.set_axis_off()
ax_ang.imshow(np.angle(grad), cmap='hsv') # hsv is cyclic, like angles
ax_ang.set_title('Gradient orientation')
ax_ang.set_axis_off()
fig.show()
import ipdb; ipdb.set_trace()
