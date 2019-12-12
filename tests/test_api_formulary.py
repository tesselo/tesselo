import io

import numpy
from guardian.shortcuts import assign_perm, remove_perm
from PIL import Image
from raster.models import RasterTile
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from rest_framework import status

from classify.models import PredictedLayer
from django.contrib.auth.models import User
from django.contrib.gis.gdal import GDALRaster
from django.core.files import File
from django.test import TestCase
from django.urls import reverse
from formulary.models import Formula, PredictedLayerFormula
from sentinel.models import Composite


class TileViewsTests(TestCase):

    def setUp(self):
        self.formula_continuous = Formula.objects.create(
            name='Banana Yellow',
            formula='B4*B4',
            breaks=0,
            min_val=0,
            max_val=WEB_MERCATOR_TILESIZE ** 2,
        )
        self.formula_discrete = Formula.objects.create(
            name='Banana Yellow',
            formula='B4*B4',
            breaks=10,
            min_val=0,
            max_val=3000,
        )
        self.formula_rgb = Formula.objects.create(
            name='Banana RGB',
            rgb=True,
            rgb_enhance_brightness=0,
            rgb_enhance_sharpness=0,
            rgb_enhance_color=0,
            rgb_enhance_contrast=0,
            rgb_scale_min=0,
            rgb_scale_max=3000,
            rgb_alpha=False,
        )
        self.formula_rgb_enhanced_alpha = Formula.objects.create(
            name='Banana Formula RGB',
            rgb=True,
            rgb_enhance_brightness=1.0,
            rgb_enhance_sharpness=1.0,
            rgb_enhance_color=1.0,
            rgb_enhance_contrast=1.0,
            rgb_scale_min=10,
            rgb_scale_max=2000,
            rgb_alpha=True,
        )
        self.composite = Composite.objects.create(
            name='Bananastand December 2015',
            official=True,
            min_date='2015-12-01',
            max_date='2015-12-31',
        )

        layers = [
            self.composite.compositeband_set.get(band='B04.jp2').rasterlayer,
            self.composite.compositeband_set.get(band='B03.jp2').rasterlayer,
            self.composite.compositeband_set.get(band='B02.jp2').rasterlayer,
        ]

        for i in range(3):
            tile_rst = GDALRaster({
                'name': '/vsimem/testtile{}.tif'.format(i),
                'driver': 'tif',
                'srid': WEB_MERCATOR_SRID,
                'width': WEB_MERCATOR_TILESIZE,
                'height': WEB_MERCATOR_TILESIZE,
                'origin': (11833687.0, -469452.0),
                'scale': (1, -1),
                'datatype': 1,
                'bands': [{'nodata_value': 0, 'data': range(WEB_MERCATOR_TILESIZE ** 2)}],
            })
            tile_rst = File(io.BytesIO(tile_rst.vsi_buffer), name='tile{}.tif'.format(i))
            self.tile = RasterTile.objects.create(
                rasterlayer=layers[i],
                rast=tile_rst,
                tilex=1234,
                tiley=1234,
                tilez=11,
            )

        self.michael = User.objects.create_user(
            username='michael',
            email='michael@bluth.com',
            password='bananastand',
        )

        self.client.login(username='michael', password='bananastand')
        assign_perm('view_formula', self.michael, self.formula_rgb)
        assign_perm('view_formula', self.michael, self.formula_discrete)
        assign_perm('view_formula', self.michael, self.formula_continuous)
        assign_perm('view_formula', self.michael, self.formula_rgb_enhanced_alpha)
        assign_perm('view_composite', self.michael, self.composite)

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
        self.assertEqual(tuple(img[0][1]), (215, 48, 39, 255))

    def test_formula_tms_rgb(self):
        url = reverse('formula_algebra-list', kwargs={
            'formula_id': self.formula_rgb.id,
            'layer_type': 'composite',
            'layer_id': self.composite.id,
            'z': 11, 'x': 1234, 'y': 1234, 'frmt': 'png'
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        img = numpy.asarray(Image.open(io.BytesIO(response.content)))
        self.assertEqual(img.shape, (256, 256, 3))
        self.assertEqual(img[1][253][1], 21)

    def test_formula_tms_rgb_enhance_alpha(self):
        url = reverse('formula_algebra-list', kwargs={
            'formula_id': self.formula_rgb_enhanced_alpha.id,
            'layer_type': 'composite',
            'layer_id': self.composite.id,
            'z': 11, 'x': 1234, 'y': 1234, 'frmt': 'png'
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        img = numpy.asarray(Image.open(io.BytesIO(response.content)))
        self.assertEqual(img.shape, (256, 256, 4))
        self.assertEqual(img[1][253][1], 30)

    def test_formula_tms_rgb_enhance_alpha_tif(self):
        url = reverse('formula_algebra-list', kwargs={
            'formula_id': self.formula_rgb_enhanced_alpha.id,
            'layer_type': 'composite',
            'layer_id': self.composite.id,
            'z': 11, 'x': 1234, 'y': 1234, 'frmt': 'tif'
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'image/tiff')
        img = numpy.asarray(Image.open(io.BytesIO(response.content)))
        self.assertEqual(img.shape, (256, 256, 3))
        self.assertEqual(img[1][235][1], 235)

    def test_formula_tms_permissions(self):
        url = reverse('formula_algebra-list', kwargs={
            'formula_id': self.formula_rgb_enhanced_alpha.id,
            'layer_type': 'composite',
            'layer_id': self.composite.id,
            'z': 11, 'x': 1234, 'y': 1234, 'frmt': 'tif'
        })

        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        remove_perm('view_formula', self.michael, self.formula_rgb_enhanced_alpha)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        assign_perm('view_formula', self.michael, self.formula_rgb_enhanced_alpha)
        remove_perm('view_composite', self.michael, self.composite)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_formula_tms_predictedlayer(self):
        # Create and populated predictedlayer.
        predictedlayer = PredictedLayer.objects.create()
        tile_rst = GDALRaster({
            'name': '/vsimem/testtile_pred.tif',
            'driver': 'tif',
            'srid': WEB_MERCATOR_SRID,
            'width': WEB_MERCATOR_TILESIZE,
            'height': WEB_MERCATOR_TILESIZE,
            'origin': (11833687.0, -469452.0),
            'scale': (1, -1),
            'datatype': 1,
            'bands': [{'nodata_value': 0, 'data': range(WEB_MERCATOR_TILESIZE ** 2)}],
        })
        tile_rst = File(io.BytesIO(tile_rst.vsi_buffer), name='tile_pred.tif')
        RasterTile.objects.create(
            rasterlayer=predictedlayer.rasterlayer,
            rast=tile_rst,
            tilex=1234,
            tiley=1234,
            tilez=11,
        )
        PredictedLayerFormula.objects.create(
            formula=self.formula_continuous,
            predictedlayer=predictedlayer,
            key='Bananastand',
        )
        self.formula_continuous.formula = 'B4*B4+2*Bananastand'
        self.formula_continuous.save()
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
        self.assertEqual(img[1][253][1], 155)
