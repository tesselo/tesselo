# # Semi-clear Scenes
# S2A_MSIL1C_20180115T103351_N0206_R108_T30NUN_20180115T154601 ok
# S2A_MSIL1C_20180125T103321_N0206_R108_T30NUN_20180125T154837 ok
# S2B_MSIL1C_20171231T103429_N0206_R108_T30NUN_20171231T123549
#
# # Small clouds
# S2B_MSIL1C_20180120T103339_N0206_R108_T30NUN_20180120T123935
# S2A_MSIL1C_20180115T103351_N0206_R108_T30NUN_20180115T154601

gdalwarp -of GTiff\
 -overwrite\
 -cutline /home/tam/Desktop/ivory_coast_clip.shp\
 -cl ivory_coast_clip\
 --config GDALWARP_IGNORE_BAD_CUTLINE YES\
 -crop_to_cutline /home/tam/Desktop/S2A_MSIL2A_20180125T103321_N0206_R108_T30NUN_20180125T154837.SAFE/GRANULE/L2A_T30NUN_A013547_20180125T104639/IMG_DATA/R10m/L2A_T30NUN_20180125T103321_TCI_10m.jp2\
 /home/tam/Desktop/ivory_coast_rgb.tif


 gdalwarp -of GTiff\
  -overwrite\
  -cutline /home/tam/Desktop/ivory_coast_clip.shp\
  -cl ivory_coast_clip\
  --config GDALWARP_IGNORE_BAD_CUTLINE YES\
  -crop_to_cutline /home/tam/Desktop/S2A_MSIL2A_20180125T103321_N0206_R108_T30NUN_20180125T154837.SAFE/GRANULE/L2A_T30NUN_A013547_20180125T104639/IMG_DATA/R10m/L2A_T30NUN_20180125T103321_B08_10m.jp2\
  /home/tam/Desktop/ivory_coast_B08.tif


  gdalwarp -of GTiff\
   -overwrite\
   -cutline /home/tam/Desktop/ivory_coast_clip.shp\
   -cl ivory_coast_clip\
   --config GDALWARP_IGNORE_BAD_CUTLINE YES\
   -crop_to_cutline /home/tam/Desktop/S2A_MSIL2A_20180125T103321_N0206_R108_T30NUN_20180125T154837.SAFE/GRANULE/L2A_T30NUN_A013547_20180125T104639/IMG_DATA/R10m/L2A_T30NUN_20180125T103321_B04_10m.jp2\
   /home/tam/Desktop/ivory_coast_B04.tif

   gdal_translate -ot Float32 /home/tam/Desktop/ivory_coast_B08.tif /home/tam/Desktop/ivory_coast_B08_float.tif
   gdal_translate -ot Float32 /home/tam/Desktop/ivory_coast_B04.tif /home/tam/Desktop/ivory_coast_B04_float.tif


  gdal_calc.py\
   -A /home/tam/Desktop/ivory_coast_B04_float.tif\
   -B /home/tam/Desktop/ivory_coast_B08_float.tif\
   --NoDataValue=0\
   --overwrite\
   --outfile=/home/tam/Desktop/ivory_coast_ndvi.tif\
   --calc="(A+B)/2"
