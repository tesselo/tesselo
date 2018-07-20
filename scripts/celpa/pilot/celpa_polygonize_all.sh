#!/bin/bash

path="/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/"

echo "Removing file previous files."
rm -rf ${path}polygonized/*

for REGION in evora faro santarem leiria aveiro castelo-branco
do
  echo "Processing $REGION"
  for LAYER in fonfo-predicted-rf age-predicted-rfr predicted-svm
  do
    echo "Processing $LAYER"

    file_base="sentinel-$REGION-$LAYER"

    if [ $LAYER = "fonfo-predicted-rf" ]; then
      gdal_polygonize.py\
          ${path}${file_base}.tif\
          -f "ESRI Shapefile"\
          ${path}polygonized/${file_base}\
          ${file_base}
    else
      gdal_calc.py -A ${path}sentinel-${REGION}-fonfo-predicted-rf.tif --outfile=${path}fonfomask.tif --calc="A>1" --NoDataValue=0
      gdal_polygonize.py\
          ${path}${file_base}.tif\
          -f "ESRI Shapefile"\
          -mask ${path}fonfomask.tif\
          ${path}polygonized/${file_base}\
          ${file_base}
      rm -f ${path}fonfomask.tif
    fi

    combined_file=${path}/polygonized/sentinel-${LAYER}.shp

    if [ ! -f "$combined_file" ]; then
        ogr2ogr -f "ESRI Shapefile" $combined_file ${path}polygonized/${file_base}/${file_base}.shp
    else
        ogr2ogr -f "ESRI Shapefile" -update -append $combined_file ${path}polygonized/${file_base}/${file_base}.shp
    fi
  done
done

python3 /home/tam/Documents/repos/tesselo/scripts/celpa_polygonized_name_field.py
