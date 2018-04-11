import datetime

from django.test import TestCase
from naip.models import NAIPQuadrangle
from naip.tasks import ingest_naip_prefix
from naip.utils import get_quadrangles_from_coords


class NAIPQuadrangleTests(TestCase):

    def setUp(self):
        NAIPQuadrangle.objects.bulk_create([
            ingest_naip_prefix('al/2013/1m/rgb/30085/m_3008501_nw_16_1_20130928.tif'),
            ingest_naip_prefix('al/2013/1m/rgb/30085/m_3008501_ne_16_1_20130928.tif'),
            ingest_naip_prefix('al/2013/1m/rgb/30085/m_3008501_sw_16_1_20130928.tif'),
            ingest_naip_prefix('al/2013/1m/rgb/30085/m_3008501_se_16_1_20130928.tif'),
            ingest_naip_prefix('al/2013/1m/rgb/30085/m_3008502_nw_16_1_20130928.tif'),

            ingest_naip_prefix('al/2015/1m/rgb/30085/m_3008501_nw_16_1_20151014.tif'),
            ingest_naip_prefix('al/2015/1m/rgb/30085/m_3008501_ne_16_1_20151014.tif'),
            ingest_naip_prefix('fl/2015/1m/rgb/30085/m_3008501_sw_16_1_20150920.tif'),
            ingest_naip_prefix('fl/2015/1m/rgb/30085/m_3008501_se_16_1_20150920.tif'),
            ingest_naip_prefix('fl/2015/1m/rgb/30085/m_3008502_nw_16_1_20151008.tif'),

        ])

    def test_naip_ingestion(self):
        naip = NAIPQuadrangle.objects.get(prefix='al/2013/1m/rgb/30085/m_3008501_nw_16_1_20130928.tif')
        self.assertEqual(naip.state, 'al')
        self.assertEqual(naip.date, datetime.date(2013, 9, 28))
        self.assertEqual(naip.resolution, '1m')
        self.assertEqual(naip.subquad, 1)
        self.assertEqual(naip.lat, 30)
        self.assertEqual(naip.lon, -85)
        self.assertEqual(naip.source, NAIPQuadrangle.RGB)

    def test_naip_quadrangle_from_coords(self):

        # 3008502_nw
        naip = get_quadrangles_from_coords(-85.8402, 30.9653).first()
        self.assertEqual(
            naip.prefix,
            'al/2013/1m/rgb/30085/m_3008502_nw_16_1_20130928.tif',
        )
        # 3008501_nw
        naip = get_quadrangles_from_coords(-85.97254, 30.96909).first()
        self.assertEqual(
            naip.prefix,
            'al/2013/1m/rgb/30085/m_3008501_nw_16_1_20130928.tif',
        )
        # 3008501_ne
        naip = get_quadrangles_from_coords(-85.9005, 30.9630).first()
        self.assertEqual(
            naip.prefix,
            'al/2013/1m/rgb/30085/m_3008501_ne_16_1_20130928.tif',
        )
        # 3008501_sw
        naip = get_quadrangles_from_coords(-85.97765, 30.87915).first()
        self.assertEqual(
            naip.prefix,
            'al/2013/1m/rgb/30085/m_3008501_sw_16_1_20130928.tif',
        )
        # 3008501_se
        naip = get_quadrangles_from_coords(-85.88403, 30.87762).first()
        self.assertEqual(
            naip.prefix,
            'al/2013/1m/rgb/30085/m_3008501_se_16_1_20130928.tif',
        )
