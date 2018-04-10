from django.core.management.base import BaseCommand
from naip.tasks import ingest_naip_index


class Command(BaseCommand):

    help = 'Ingest NAIP manifest data.'

    def handle(self, *args, **options):
        # Write start message.
        self.stdout.write(self.style.SUCCESS('Ingesting NAIP manifest file.'))
        # Run function.
        ingest_naip_index()
        # Write success message.
        self.stdout.write(self.style.SUCCESS('Finished ingesting NAIP manifest file successfully.'))
