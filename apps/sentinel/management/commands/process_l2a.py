from django.core.management.base import BaseCommand
from sentinel.tasks import process_l2a


class Command(BaseCommand):
    help = 'Upgrades a Sentinel Tile to L2A.'

    def add_arguments(self, parser):
        parser.add_argument('sentineltile_id', nargs='+', type=int)

    def handle(self, *args, **options):
        for sentineltile_id in options['sentineltile_id']:
            process_l2a(sentineltile_id)
            self.stdout.write(self.style.SUCCESS('Successfully processed SentinelTile "%s"' % sentineltile_id))
