from django.core.management.base import BaseCommand
from sentinel.const import FARGATE_COMMAND_BASE
from sentinel.tasks import process_l2a, drive_sentinel_bucket_parser, sync_sentinel_bucket_utm_zone, get_aggregation_area_scenes, build_composite


class Command(BaseCommand):

    help = 'Run sentinel data process tasks.'

    funks = {
        'drive_sentinel_bucket_parser': drive_sentinel_bucket_parser,
        'sync_sentinel_bucket_utm_zone': sync_sentinel_bucket_utm_zone,
        'process_l2a': process_l2a,
        'build_composite': build_composite,
    }

    def add_arguments(self, parser):
        parser.add_argument('command', nargs=1, type=str)
        parser.add_argument('command_args', nargs='*', type=str)

    def handle(self, *args, **options):
        # Select task function to run.
        funk = self.funks[options['command'][0]]
        # Run function.
        funk(*options['command_args'])
        # Return success message.
        self.stdout.write(self.style.SUCCESS('Successfully processed task {} with args {}'.format(options['command'][0], options['command_args'])))
