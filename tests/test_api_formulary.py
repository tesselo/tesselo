import io

import numpy
from PIL import Image
from raster.models import RasterTile
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from rest_framework import status

from django.contrib.auth.models import User
from django.contrib.gis.gdal import GDALRaster
from django.core.files import File
from django.test import TestCase
from django.urls import reverse
from formulary.models import Formula
from sentinel.models import Composite


class TileViewsTests(TestCase):

    def setUp(self):
        self.formula_continuous = Formula.objects.create(
            name='Banana Yellow',
            formula='B5*B5',
            breaks=0,
            min_val=0,
            max_val=WEB_MERCATOR_TILESIZE ** 2,
        )
        self.formula_discrete = Formula.objects.create(
            name='Banana Yellow',
            formula='B5*B5',
            breaks=10,
            min_val=0,
            max_val=3000,
        )

        self.composite = Composite.objects.create(
            name='Bananastand December 2015',
            official=True,
            min_date='2015-12-01',
            max_date='2015-12-31',
        )

        self.layer = self.composite.compositeband_set.get(band='B05.jp2').rasterlayer

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

    def test_formula_tms_algebra_continuous(self):
        url = reverse('formula_algebra-list', kwargs={
            'formula_id': self.formula_continuous.id,
            'layer_type': 'composite',
            'layer_id': self.composite.id,
            'z': 11, 'x': 1234, 'y': 1234, 'frmt': 'png'
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        img = numpy.asarray(Image.open(io.BytesIO(response.content)))
        self.assertEqual(img.shape, (256, 256, 4))
        self.assertEqual(img[1][253][1], 156)

    def test_formula_tms_algebra_discrete(self):
        url = reverse('formula_algebra-list', kwargs={
            'formula_id': self.formula_discrete.id,
            'layer_type': 'composite',
            'layer_id': self.composite.id,
            'z': 11, 'x': 1234, 'y': 1234, 'frmt': 'png'
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        img = numpy.asarray(Image.open(io.BytesIO(response.content)))
        self.assertEqual(img.shape, (256, 256, 4))
        self.assertEqual(img[1][253][1], 104)
