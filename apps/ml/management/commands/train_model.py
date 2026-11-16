from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Train, evaluate and register the sales prediction model."

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("train_model is not implemented yet - build apps/ml/train.py first."))
