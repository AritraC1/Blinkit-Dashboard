from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the Blinkit ETL pipeline (Excel -> cleaned -> database)."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("run_etl is not implemented yet - build apps/etl/pipeline.py first."))
