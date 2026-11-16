"""Tests: prediction runs end to end; unseen categories do not crash it."""

from pathlib import Path
import tempfile

import pandas as pd
from django.test import TestCase, override_settings

from apps.ml.models import ModelRun
from apps.ml.registry import register
from apps.ml.train import train


def make_synthetic_frame() -> pd.DataFrame:
    """18 rows: 6 items x 3 outlets, sales driven by weight and outlet.

    Grouped by item_id, exactly like the real data, so a random split would
    leak weight knowledge across the split and inflate the scores.
    """
    items = [
        {"item_id": "FDA01", "item_type": "Dairy", "fat_content": "Low Fat",
         "category": "Food", "weight": 5.0},
        {"item_id": "FDA02", "item_type": "Dairy", "fat_content": "Regular",
         "category": "Food", "weight": 7.5},
        {"item_id": "DRB01", "item_type": "Soft Drinks", "fat_content": "Low Fat",
         "category": "Drink", "weight": 4.0},
        {"item_id": "DRB02", "item_type": "Soft Drinks", "fat_content": "Regular",
         "category": "Drink", "weight": 6.5},
        {"item_id": "NCC01", "item_type": "Household", "fat_content": "Non-Edible",
         "category": "Non-Consumable", "weight": 9.0},
        {"item_id": "NCC02", "item_type": "Household", "fat_content": "Non-Edible",
         "category": "Non-Consumable", "weight": 11.0},
    ]
    outlets = [
        {"outlet_id": "OUT01", "establishment_year": 2016, "location_tier": "Tier 1",
         "outlet_type": "Supermarket Type1", "outlet_size": "Small"},
        {"outlet_id": "OUT02", "establishment_year": 2018, "location_tier": "Tier 2",
         "outlet_type": "Grocery Store", "outlet_size": "Medium"},
        {"outlet_id": "OUT03", "establishment_year": 2020, "location_tier": "Tier 3",
         "outlet_type": "Supermarket Type2", "outlet_size": "High"},
    ]
    rows = []
    for item in items:
        for outlet in outlets:
            rows.append(
                {
                    **item,
                    **outlet,
                    "visibility": 0.1,
                    "rating": 4.0,
                    "sales": item["weight"] * 10 + 100.0,
                }
            )
    return pd.DataFrame(rows)


class TrainAndRegisterTests(TestCase):
    """Training part: a small synthetic frame produces one active registered model."""

    def test_training_registers_one_active_model(self):
        bundle = train(make_synthetic_frame())
        with tempfile.TemporaryDirectory() as tmp, override_settings(ML_ARTIFACTS_DIR=Path(tmp)):
            run = register(bundle, notes="synthetic safety net")

            self.assertEqual(ModelRun.objects.count(), 1)
            self.assertEqual(ModelRun.objects.filter(is_active=True).count(), 1)
            self.assertEqual(run.pk, ModelRun.objects.get(is_active=True).pk)
            # The artifact really exists on disk.
            self.assertTrue(Path(run.artifact_path).exists())
            # Every registered fact made it into the row.
            self.assertEqual(set(run.metrics), {"r2", "mae", "rmse"})
            self.assertEqual(run.feature_list, bundle["feature_list"])
            # The raw item ID must never be a feature (1,559 values = memorisation).
            self.assertNotIn("item_id", run.feature_list)
            for payload in ("actual_vs_predicted", "residual_quantiles", "feature_importances"):
                self.assertIn(payload, run.evaluation)

    def test_new_registration_deactivates_the_previous_one(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(ML_ARTIFACTS_DIR=Path(tmp)):
            first = register(train(make_synthetic_frame()))
            second = register(train(make_synthetic_frame()), notes="second run")

            first.refresh_from_db()
            second.refresh_from_db()
            self.assertFalse(first.is_active)
            self.assertTrue(second.is_active)
            self.assertEqual(ModelRun.objects.filter(is_active=True).count(), 1)
