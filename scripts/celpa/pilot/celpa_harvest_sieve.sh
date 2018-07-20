#!/bin/bash

for DATE in '2016-12-06' '2016-12-26' '2017-01-05' '2017-01-15' '2017-01-25' '2017-02-24' '2017-03-16' 'total'
do
    echo "Processing $DATE"

    gdalwarp -of GTiff\
     -overwrite\
     -cutline /media/tam/rhino/work/projects/tesselo/celpa/celpa_data/gorgulho_leiria.shp\
     -cl gorgulho_leiria\
     --config GDALWARP_IGNORE_BAD_CUTLINE YES\
     -crop_to_cutline /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/harvest/sentinel-${DATE}-fonfo-diff-rf.tif\
     /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/harvest/clip/sentinel-${DATE}-fonfo-diff-clip-rf.tif

    # gdal_sieve.py -st 1500 -4 -of GTiff\
    #     /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/harvest/sentinel-${DATE}-fonfo-diff-rf.tif\
    #     /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/harvest/sentinel-${DATE}-fonfo-diff-sieve-rf.tif
done
