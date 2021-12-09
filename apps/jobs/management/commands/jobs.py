from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):

    help = 'Run data process tasks.'

    def __init__(self, *args, **kwargs):
        print("Initializing Base Command")
        super().__init__(*args, **kwargs)

    def add_arguments(self, parser):
        parser.add_argument('command', nargs=1, type=str)
        parser.add_argument('command_args', nargs='*', type=str)

    def handle(self, *args, **options):
        # Write start message.
        if not settings.LOCAL:
            self.stdout.write(self.style.SUCCESS('Running task {} with args {}'.format(options['command'][0], options['command_args'])))

        from raster_aggregation.tasks import aggregation_layer_parser

        from classify.collectpixels import (
            combine_trainingpixels_patches, populate_trainingpixels, populate_trainingpixels_patch
        )
        from classify.tasks import (
            build_predicted_pyramid, predict_sentinel_chunk, predict_sentinel_layer, sieve_sentinel_chunk,
            train_sentinel_classifier
        )
        from naip.tasks import ingest_naip_manifest
        from report.tasks import populate_report
        from sentinel.tasks import (
            clear_composite, clear_sentineltile, composite_build_callback, drive_sentinel_bucket_parser,
            process_compositetile, process_l2a, push_scheduled_composite_builds, sync_sentinel_bucket_utm_zone
        )
        from sentinel_1.tasks import parse_s3_sentinel_1_inventory, snap_terrain_correction

        funks = {
            'drive_sentinel_bucket_parser': drive_sentinel_bucket_parser,
            'sync_sentinel_bucket_utm_zone': sync_sentinel_bucket_utm_zone,
            'process_l2a': process_l2a,
            'process_compositetile': process_compositetile,
            'clear_sentineltile': clear_sentineltile,
            'clear_composite': clear_composite,
            'composite_build_callback': composite_build_callback,
            'train_sentinel_classifier': train_sentinel_classifier,
            'predict_sentinel_layer': predict_sentinel_layer,
            'predict_sentinel_chunk': predict_sentinel_chunk,
            'sieve_sentinel_chunk': sieve_sentinel_chunk,
            'build_predicted_pyramid': build_predicted_pyramid,
            'ingest_naip_manifest': ingest_naip_manifest,
            'push_scheduled_composite_builds': push_scheduled_composite_builds,
            'populate_report': populate_report,
            'parse_aggregationlayer': aggregation_layer_parser,
            'parse_s3_sentinel_1_inventory': parse_s3_sentinel_1_inventory,
            'snap_terrain_correction': snap_terrain_correction,
            'populate_trainingpixels': populate_trainingpixels,
            'populate_trainingpixels_patch': populate_trainingpixels_patch,
            'combine_trainingpixels_patches': combine_trainingpixels_patches,
        }

        # Select task function to run.
        funk = funks[options['command'][0]]
        # Run function.
        funk(*options['command_args'])
        # Write success message.
        if not settings.LOCAL:
            self.stdout.write(self.style.SUCCESS('Finished task successfully.'))
