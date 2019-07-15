from unittest.mock import patch

from raster_aggregation.models import AggregationArea, AggregationLayer

from django.test import TestCase
from sentinel.models import (
    Composite, CompositeBuild, CompositeBuildSchedule, MGRSTile, SentinelTile, SentinelTileAggregationLayer
)
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


def patch_process_l2a(stile_id):
    """
    Fake ingest sentinel tile.
    """
    SentinelTile.objects.filter(id=stile_id).update(status=SentinelTile.FINISHED)


@patch('sentinel.tasks.ingest_tile_from_prefix', patch_ingest_tile_from_prefix)
@patch('sentinel.tasks.ecs.process_l2a', patch_process_l2a)
class SnsMessageProcessingTest(TestCase):

    def setUp(self):
        # Create composite build objects.
        agglayer = AggregationLayer.objects.create(name='Test Agg Layer')
        AggregationArea.objects.create(
            name='Test Agg Area',
            aggregationlayer=agglayer,
            geom='SRID=3857;MULTIPOLYGON((( 11833687.0 -469452.0, 11833787.0 -469452.0, 11833787.0 -469352.0, 11833687.0 -469352.0, 11833687.0 -469452.0)))'
        )
        composite = Composite.objects.create(
            name='The World',
            official=True,
            min_date='2019-01-01',
            max_date='2019-02-01',
        )
        build = CompositeBuild.objects.create(
            composite=composite,
            aggregationlayer=agglayer,
        )
        schedule = CompositeBuildSchedule.objects.create(
            interval=CompositeBuildSchedule.WEEKLY,
            delay_build_days=1,
            continuous_scene_ingestion=False,
        )
        schedule.compositebuilds.add(build)

        # Fake SNS message.
        self.msg = {
            'Records': [{
                'Sns': {
                    'Message': '{"tiles": [{"path": "tiles/10/S/DG/2015/12/7/0"}]}'
                }
            }]
        }

    def test_sns_s2_processing(self):
        """
        Test automatic scene aggregationlayer registration.
        """
        process_sentinel_sns_message(self.msg, {})
        # Tile has been created.
        self.assertEqual(SentinelTile.objects.count(), 1)
        self.assertEqual(SentinelTile.objects.first().status, SentinelTile.UNPROCESSED)
        # Tile has been associated with aggregation layer.
        self.assertEqual(SentinelTileAggregationLayer.objects.count(), 1)

    def test_sns_s2_processing_automatic_ingestion(self):
        """
        Test automatic scene ingestion trigger.
        """
        CompositeBuildSchedule.objects.all().update(continuous_scene_ingestion=True)
        process_sentinel_sns_message(self.msg, {})
        # Tile has been ingested.
        self.assertEqual(SentinelTile.objects.first().status, SentinelTile.FINISHED)
