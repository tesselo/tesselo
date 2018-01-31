import os

import dbf

os.system('''gdal_polygonize.py\
    /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/harvest/clip/sentinel-total-fonfo-diff-clip-rf.tif\
    -f "ESRI Shapefile"\
    /media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/harvest/clip\
    celpa_harvest_detection''')

shp = "/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports/harvest/clip/celpa_harvest_detection.dbf"

type_dict = {
    1: "Harvest between 2016-12-06 and 2016-12-02",
    2: "Harvest between 2016-12-26 and 2017-01-05",
    3: "Harvest between 2017-01-05 and 2017-01-15",
    4: "Harvest between 2017-01-15 and 2017-01-25",
    5: "Harvest between 2017-01-25 and 2017-02-24",
    6: "Harvest between 2017-02-24 and 2017-03-16",
}

with dbf.Table(shp) as db:
    try:
        db.add_fields('Harvest C(100)')
    except:
        print('Skipping field creation.')

    print(db)

    for record in dbf.Process(db):
        print(record)
        record.harvest = type_dict[record.dn]
