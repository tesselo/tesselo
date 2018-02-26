from django.core.management.base import BaseCommand
from sentinel.tasks import (
    composite_build_callback, drive_sentinel_bucket_parser, process_compositetile, process_l2a,
    sync_sentinel_bucket_utm_zone
)


class Command(BaseCommand):

    help = 'Run sentinel data process tasks.'

    funks = {
        'drive_sentinel_bucket_parser': drive_sentinel_bucket_parser,
        'sync_sentinel_bucket_utm_zone': sync_sentinel_bucket_utm_zone,
        'process_l2a': process_l2a,
        'process_compositetile': process_compositetile,
        'composite_build_callback': composite_build_callback,
    }

    def add_arguments(self, parser):
        parser.add_argument('command', nargs=1, type=str)
        parser.add_argument('command_args', nargs='*', type=str)

    def handle(self, *args, **options):
        # Select task function to run.
        funk = self.funks[options['command'][0]]
        # Run function.
        cmnd = funk(*options['command_args'])
        # Return success message.
        self.stdout.write(self.style.SUCCESS('Successfully scheduled task {} with args {}'.format(options['command'][0], options['command_args'])))
        self.stdout.write(self.style.SUCCESS(''.format(cmnd)))
