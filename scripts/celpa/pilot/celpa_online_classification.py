import logging

from django.contrib.gis.gdal import DataSource
from tesselate import Tesselate

ts = Tesselate()
ts.client.set_token('c4a4a23f6a80af7e737a4fceb1cb165db521cd6c')

logging.getLogger().setLevel(logging.DEBUG)

# Get composite.
composite = ts.composite(search='November 2017')
composite = [dat for dat in composite if dat['name'] == 'November 2017'][0]
print(composite)

# Open training data set.
ds = DataSource('/media/tam/rhino/work/projects/tesselo/celpa/analysis/training/celpa_forest_type_manual.shp')
lyr = ds[0]
valuemap = {
    'euy': 1,
    'eu': 2,
    'pi': 3,
    'sob': 4,
}

# Search for classifier.
classifier_name = 'CELPA Forest Type'
classifier = ts.classifier(search=classifier_name)
if len(classifier):
    classifier = classifier[0]
else:
    classifier = ts.classifier(data={'name': classifier_name, 'algorithm': 'svm'})
print(classifier)

trainings = []

for feat in lyr:
    post = {
        'category': feat['name'].as_string(),
        'value': valuemap[feat['name'].as_string()],
        'geom': feat.geom.ewkt,
        'composite': composite['id'],
    }
    print(post)

    response = ts.trainingsample(data=post)

    trainings.append(response['id'])

classifier.update({'trainingsamples': trainings})
ts.classifier(data=classifier)

# Train the classifier
ts.train(classifier)

# Create a predicted layer
predicted = ts.predictedlayer(classifier=classifier['id'], composite=composite['id'])
if len(predicted):
    predicted = predicted[0]
else:
    predicted = ts.predictedlayer(data={
        'classifier': classifier['id'],
        'composite': composite['id'],
    })

print(predicted)

# Predict layer if classifier is trained.
ts.predict(predicted)
