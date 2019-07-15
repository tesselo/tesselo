from unittest.mock import patch

from raster_aggregation.models import AggregationArea, AggregationLayer

from django.test import TestCase
from sentinel.models import MGRSTile, SentinelTile, SentinelTileAggregationLayer
from sentinel.tasks import process_sentinel_sns_message


def patch_ingest_tile_from_prefix(tile_prefix, client=None):
    """
    Patch scene ingestion method.
    """
    mgrs = MGRSTile.objects.create(
        grid_square='UC',
        utm_zone='5',
        latitude_band='5',
        geom='SRID=3857;POLYGON(( 11833687.0 -469452.0, 11833787.0 -469452.0, 11833787.0 -469352.0, 11833687.0 -469352.0, 11833687.0 -469452.0))',
    )
    return SentinelTile.objects.create(
        prefix=tile_prefix,
        datastrip='test',
        product_name='test',
        mgrstile=mgrs,
        tile_geom='SRID=3857;POLYGON(( 11833687.0 -469452.0, 11833787.0 -469452.0, 11833787.0 -469352.0, 11833687.0 -469352.0, 11833687.0 -469452.0))',
        tile_data_geom='SRID=3857;MULTIPOLYGON((( 11833687.0 -469452.0, 11833787.0 -469452.0, 11833787.0 -469352.0, 11833687.0 -469352.0, 11833687.0 -469452.0)))',
        collected='2019-01-01',
        cloudy_pixel_percentage=0,
        data_coverage_percentage=100,
        angle_azimuth=1,
        angle_altitude=3,
    )


@patch('sentinel.tasks.ingest_tile_from_prefix', patch_ingest_tile_from_prefix)
class SnsMessageProcessingTest(TestCase):

    def setUp(self):
        agglayer = AggregationLayer.objects.create(name='Test Agg Layer')
        AggregationArea.objects.create(
            name='Test Agg Area',
            aggregationlayer=agglayer,
            geom='SRID=3857;MULTIPOLYGON((( 11833687.0 -469452.0, 11833787.0 -469452.0, 11833787.0 -469352.0, 11833687.0 -469352.0, 11833687.0 -469452.0)))'
        )

    def test_sns_s2_processing(self):
        msg = {
            'Records': [{
                'Sns': {
                    'Message': '{"tiles": [{"path": "tiles/10/S/DG/2015/12/7/0"}]}'
                }
            }]
        }
        process_sentinel_sns_message(msg, {})
        # Tile has been created.
        self.assertEqual(SentinelTile.objects.count(), 1)
        # Tile has been associated with aggregation layer.
        self.assertEqual(SentinelTileAggregationLayer.objects.count(), 1)
