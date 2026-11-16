"""Management command: run the Blinkit ETL pipeline (Excel -> cleaned -> database)."""

from django.core.management.base import BaseCommand, CommandError

from apps.etl.extract import ExtractError
from apps.etl.pipeline import PipelineError, run


class Command(BaseCommand):
    help = "Run the Blinkit ETL pipeline (Excel -> cleaned -> database)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=None,
            help="Path to a raw Excel file (defaults to settings.RAW_DATA_PATH).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Extract, transform and validate, but stop before loading.",
        )
        parser.add_argument(
            "--no-csv",
            action="store_true",
            help="Skip writing the cleaned CSV to data/processed/.",
        )

    def handle(self, *args, **options):
        try:
            summary = run(
                path=options["file"],
                dry_run=options["dry_run"],
                write_csv=not options["no_csv"],
            )
        except ExtractError as exc:
            raise CommandError(f"Extract failed: {exc}") from exc
        except PipelineError as exc:
            raise CommandError(str(exc)) from exc

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry run - nothing was loaded."))
        else:
            self.stdout.write(self.style.SUCCESS("ETL completed successfully."))

        self.stdout.write("Summary:")
        for key, value in summary.items():
            self.stdout.write(f"  {key}: {value}")
