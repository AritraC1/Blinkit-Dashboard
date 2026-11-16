from django.core.management.base import BaseCommand, CommandError

from apps.ml.features import load_sales_frame
from apps.ml.registry import register
from apps.ml.train import train


class Command(BaseCommand):
    help = "Train, evaluate and register the sales prediction model."

    def add_arguments(self, parser):
        parser.add_argument(
            "--notes", default="", help="Free-text note stored on the ModelRun."
        )
        parser.add_argument(
            "--no-activate",
            action="store_true",
            help="Register the run without making it the active model.",
        )
        parser.add_argument(
            "--with-rating",
            action="store_true",
            help="Include rating as a feature (not known before a sale - leaks the answer).",
        )
        parser.add_argument(
            "--with-outlet-size",
            action="store_true",
            help="Include outlet_size as a feature (inconsistent for 3 outlets).",
        )

    def handle(self, *args, **options):
        df = load_sales_frame()
        if df.empty:
            raise CommandError(
                "No SalesRecords found - run `uv run python manage.py run_etl` first."
            )
        self.stdout.write(
            f"Loaded {len(df)} sales records across {df['item_id'].nunique()} items."
        )

        bundle = train(
            df,
            include_rating=options["with_rating"],
            include_outlet_size=options["with_outlet_size"],
        )

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("CV scores (grouped by item)"))
        self.stdout.write(f"  {'model':<18}{'R2':>8}{'MAE':>10}{'RMSE':>10}")
        for name, scores in bundle["cv_results"].items():
            self.stdout.write(
                f"  {name:<18}{scores['r2']:>8.3f}{scores['mae']:>10.1f}{scores['rmse']:>10.1f}"
            )

        model_metrics = bundle["metrics"]
        baseline = bundle["baseline_metrics"]
        self.stdout.write("")
        self.stdout.write(
            f"Best candidate: {bundle['algorithm']} "
            f"(held out {bundle['test_size']} of {bundle['train_size'] + bundle['test_size']} rows)"
        )
        self.stdout.write(
            f"  model:    R2={model_metrics['r2']:.3f} "
            f"MAE={model_metrics['mae']:.1f} RMSE={model_metrics['rmse']:.1f}"
        )
        self.stdout.write(
            f"  baseline: R2={baseline['r2']:.3f} "
            f"MAE={baseline['mae']:.1f} RMSE={baseline['rmse']:.1f}"
        )

        run = register(bundle, notes=options["notes"], activate=not options["no_activate"])
        self.stdout.write("")
        if options["no_activate"]:
            self.stdout.write(self.style.WARNING(f"Registered {run.version} (not active)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Registered and activated {run.version}."))
