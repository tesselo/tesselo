#!/bin/bash

consolidated_file="/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/shapes/consolidated.shp"

if [ -f "$consolidated_file" ]; then
    echo "Removing previous file."
    rm -r /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/shapes/*
fi

for REGION in evora faro santarem leiria aveiro castelo-branco
do
    echo "Processing $REGION"

    gdal_sieve.py -st 8 -4 -of GTiff\
        /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/sentinel-${REGION}-predicted-svm.tif\
        /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/shapes/sentinel-${REGION}-predicted-svm-sieve.tif

    gdal_polygonize.py\
        /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/shapes/sentinel-${REGION}-predicted-svm-sieve.tif\
        -f "ESRI Shapefile"\
        /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/shapes/sentinel-${REGION}-predicted-svm\
        sentinel-${REGION}-predicted-svm


    if [ ! -f "$consolidated_file" ]; then
        ogr2ogr -f "ESRI Shapefile" $consolidated_file /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/shapes/sentinel-${REGION}-predicted-svm/sentinel-${REGION}-predicted-svm.shp
    else
        ogr2ogr -f "ESRI Shapefile" -update -append $consolidated_file /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/shapes/sentinel-${REGION}-predicted-svm/sentinel-${REGION}-predicted-svm.shp
    fi
done
        
#-mask /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/shapes/sentinel-${REGION}-predicted-svm-sieve.tif\
