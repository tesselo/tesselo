import io

import numpy
from PIL import Image
from raster.models import RasterLayer, RasterTile
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from rest_framework import status

from classify.models import PredictedLayer
from django.contrib.auth.models import User
from django.contrib.gis.gdal import GDALRaster
from django.core.files import File
from django.test import TestCase
from django.urls import reverse


class TileViewsTests(TestCase):

    def setUp(self):
        self.layer = RasterLayer.objects.create(name='Test Rasterlayer')

        tile_rst = GDALRaster({
            'name': '/vsimem/testtile.tif',
            'driver': 'tif',
            'srid': WEB_MERCATOR_SRID,
            'width': WEB_MERCATOR_TILESIZE,
            'height': WEB_MERCATOR_TILESIZE,
            'origin': (11833687.0, -469452.0),
            'scale': (1, -1),
            'datatype': 1,
            'bands': [{'nodata_value': 0, 'data': range(WEB_MERCATOR_TILESIZE ** 2)}],
        })

        tile_rst = File(io.BytesIO(tile_rst.vsi_buffer), name='tile.tif')

        self.tile = RasterTile.objects.create(
            rasterlayer=self.layer,
            rast=tile_rst,
            tilex=1234,
            tiley=1234,
            tilez=11,
        )

        User.objects.create_superuser(
            username='michael',
            email='michael@bluth.com',
            password='bananastand'
        )

        self.client.login(username='michael', password='bananastand')

    def test_simple_tile(self):
        url = reverse('tile-list', kwargs={'layer': self.layer.id, 'z': 11, 'x': 1234, 'y': 1234, 'frmt': 'png'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        img = numpy.asarray(Image.open(io.BytesIO(response.content)))
        self.assertEqual(img.shape, (256, 256, 4))
        self.assertEqual(img[1][153][1], 152)

    def test_algebra_rgb(self):
        url = reverse('algebra-list', kwargs={'z': 11, 'x': 1234, 'y': 1234, 'frmt': 'png'})
        url += '?layers=r={0},g={0},b={0}&alpha&scale=1,300'.format(self.layer.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        img = numpy.asarray(Image.open(io.BytesIO(response.content)))
        self.assertEqual(img.shape, (256, 256, 4))
        self.assertEqual(img[1][253][1], 214)

    def test_algebra_formula(self):
        url = reverse('algebra-list', kwargs={'z': 11, 'x': 1234, 'y': 1234, 'frmt': 'png'})
        url += '?layers=x={0}&formula=x*x&colormap={{"continuous": "True","range":[-1.0,1.0],"from":[165,0,38],"to":[0,104,55],"over":[249,247,174]}}'.format(self.layer.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        img = numpy.asarray(Image.open(io.BytesIO(response.content)))
        self.assertEqual(img.shape, (256, 256, 4))
        self.assertEqual(img[1][153][1], 216)

    def test_predictedlayer_tile(self):
        pred = PredictedLayer.objects.create(name='Test', rasterlayer=self.layer)
        url = reverse('predictedlayer_tile-list', kwargs={'predictedlayer_id': pred.id, 'z': 11, 'x': 1234, 'y': 1234, 'frmt': 'png'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        img = numpy.asarray(Image.open(io.BytesIO(response.content)))
        self.assertEqual(img.shape, (256, 256, 4))
        self.assertEqual(img[1][153][1], 152)
