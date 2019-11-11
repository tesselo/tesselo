from raster_aggregation.tasks import aggregation_layer_parser

from classify.tasks import (
    build_predicted_pyramid, export_training_data, predict_sentinel_chunk, predict_sentinel_layer,
    train_sentinel_classifier
)
from django.conf import settings
from django.core.management.base import BaseCommand
from naip.tasks import ingest_naip_manifest
from report.tasks import populate_report
from sentinel.tasks import (
    clear_sentineltile, composite_build_callback, drive_sentinel_bucket_parser, process_compositetile, process_l2a,
    push_scheduled_composite_builds, sync_sentinel_bucket_utm_zone
)


class Command(BaseCommand):

    help = 'Run data process tasks.'

    funks = {
        'drive_sentinel_bucket_parser': drive_sentinel_bucket_parser,
        'sync_sentinel_bucket_utm_zone': sync_sentinel_bucket_utm_zone,
        'process_l2a': process_l2a,
        'process_compositetile': process_compositetile,
        'clear_sentineltile': clear_sentineltile,
        'composite_build_callback': composite_build_callback,
        'train_sentinel_classifier': train_sentinel_classifier,
        'predict_sentinel_layer': predict_sentinel_layer,
        'predict_sentinel_chunk': predict_sentinel_chunk,
        'build_predicted_pyramid': build_predicted_pyramid,
        'export_training_data': export_training_data,
        'ingest_naip_manifest': ingest_naip_manifest,
        'push_scheduled_composite_builds': push_scheduled_composite_builds,
        'populate_report': populate_report,
        'parse_aggregationlayer': aggregation_layer_parser,
    }

    def add_arguments(self, parser):
        parser.add_argument('command', nargs=1, type=str)
        parser.add_argument('command_args', nargs='*', type=str)

    def handle(self, *args, **options):
        # Write start message.
        if not settings.LOCAL:
            self.stdout.write(self.style.SUCCESS('Running task {} with args {}'.format(options['command'][0], options['command_args'])))
        # Select task function to run.
        funk = self.funks[options['command'][0]]
        # Run function.
        funk(*options['command_args'])
        # Write success message.
        if not settings.LOCAL:
            self.stdout.write(self.style.SUCCESS('Finished task successfully.'))
