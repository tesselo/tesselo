#!/bin/bash

source_file="/media/tam/rhino/work/projects/tesselo/celpa/cos/cos_pt_2015.shp"
centroid_file="/media/tam/rhino/work/projects/tesselo/celpa/cos/centroids/centroids_cos_pt_2015.shp"
sample_file="/media/tam/rhino/work/projects/tesselo/celpa/cos/centroids/centroid_sample_cos_pt_2015.shp"
buffer_file="/media/tam/rhino/work/projects/tesselo/celpa/cos/centroids/centroid_sample_buffer_cos_pt_2015.shp"

echo "Preparing centroids"
ogr2ogr -overwrite -lco ENCODING=ISO-8859-1 -sql "SELECT ST_PointOnSurface(geometry), substr(COS2015_V1, 1, 1) AS level1, substr(COS2015_V1, 1, 3) AS level2, substr(COS2015_V1, 1, 5) AS level3, substr(COS2015_V1, 1, 8) AS level4, * FROM cos_pt_2015" -dialect sqlite $centroid_file $source_file

for CLASS in 1.1 1.2 2.1 2.2 2.3 3.1 3.2 3.3 4.0 5.1 5.2
do
  if [ $CLASS = 1.1 ]; then
    mode="-overwrite"
  else
    mode="-append"
  fi
  # For forests, sample more.
  if [ $CLASS = 3.1 ]; then
    ssize=500
  else
    ssize=100
  fi
  echo "Sampling $ssize pixels for class $CLASS"
  ogr2ogr $mode -sql "SELECT * FROM centroids_cos_pt_2015 WHERE level2 = '$CLASS' ORDER BY Random() LIMIT $ssize" -dialect sqlite $sample_file $centroid_file
done

echo "Creating tiny 1mm squared buffers"
ogr2ogr -overwrite -sql "SELECT ST_Buffer(geometry, 0.001, 1), * FROM centroid_sample_cos_pt_2015" -dialect sqlite $buffer_file $sample_file
