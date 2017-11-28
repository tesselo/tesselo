import os
import pickle

import tesselate

os.chdir('/media/tam/rhino/work/projects/tesselo/celpa/analysis/sentinel_exports')

# Create initial regions dict.
regions = {
    'Celpa Aveiro': {'scene_id': 138595, 'scene_date': '2017/11/16'},
    'Celpa Castelo Branco': {'scene_id': 139061, 'scene_date': '2017/11/16'},
    'Celpa Evora': {'scene_id': 140004, 'scene_date': '2017/11/16'},
    'Celpa Faro': {'scene_id': 138255, 'scene_date': '2017/11/16'},
    'Celpa Leiria': {'scene_id': 138259, 'scene_date': '2017/11/16'},
    'Celpa Santarem': {'scene_id': 138239, 'scene_date': '2017/11/16'},
}

for region, dat in regions.items():
    region_key = '-'.join(region.split(' ')[1:]).lower()
    print(region_key)

    tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')

    # Get scene.
    dat['scene'] = tess.get_scene(dat['scene_id'])
    # Get aggregationlayers
    dat['agglayers'] = tess.get_aggregationlayers(region)
    # Reduce to first one found.
    dat['agglayer'] = dat['agglayers'][0]
    dat['bbox'] = tess.aggregationlayer_bbox(dat['agglayer'])
    # Get targets from api.
    dat['targets'] = tess.create_target_rasters(dat['bbox'], region_key=region_key)
    tess.load_tile_data(dat['targets'], dat['bbox'], dat['scene'])
    tess.export_rgb(dat['targets'], dat['bbox'], region_key)

with open('regions.pickle', 'wb') as f:
    pickle.dump(regions, f)

regions = pickle.load(open('regions.pickle', 'rb'))

for region, dat in regions.items():
    region_key = '-'.join(region.split(' ')[1:]).lower()
    print(region_key)
    tess = tesselate.Tesselo('570d10aec18ae6e72ddbe3a9b3a5b9345cbc53b9')

    # Get targets from disk.
    dat['targets'] = tess.read_target_rasters_from_disk(region_key)

    # Create training dataset.
    tess.construct_training_data(dat['targets'], dat['agglayer'], -5)
    # tess.construct_training_data(dat['targets'], '/media/tam/rhino/work/projects/tesselo/celpa/analysis/training/santarem_manual_polygons.shp', -20)

    # Classify and predict.
    for algo in ('nn', 'svm', 'rf'):
        print('Classifying', algo)
        tess.classify(splitfraction=0.75, clf_name=algo)
        tess.accuracy()
        print('Predicting', algo)
        tess.predict_raster(dat['targets'], dat['bbox'], algo, region_key)
        dat['clf-{}'.format(algo)] = tess.clf
