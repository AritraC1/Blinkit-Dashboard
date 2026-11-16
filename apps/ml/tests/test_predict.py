"""Tests: prediction runs end to end; unseen categories do not crash it."""

from pathlib import Path
import tempfile

import pandas as pd
from django.test import TestCase, override_settings

from apps.ml.models import ModelRun, PredictionLog
from apps.ml import predict, registry
from apps.ml.predict import InvalidInputError, NotTrainedError
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


def valid_inputs(**overrides) -> dict:
    """A request that passes validation; overrides tweak one field at a time."""
    inputs = {
        "item_type": "Dairy",
        "fat_content": "Low Fat",
        "category": "Food",
        "weight": 7.5,
        "visibility": 0.1,
        "outlet_type": "Supermarket Type1",
        "location_tier": "Tier 1",
        "establishment_year": 2016,
    }
    inputs.update(overrides)
    return inputs


class PredictSalesTests(TestCase):
    """The what-if prediction: valid input predicts and logs, bad input is rejected."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.TemporaryDirectory()
        cls._override = override_settings(ML_ARTIFACTS_DIR=Path(cls._tmp.name))
        cls._override.enable()
        registry._CACHE.clear()
        cls.active_run = register(train(make_synthetic_frame()), notes="predict tests")

    @classmethod
    def tearDownClass(cls):
        registry._CACHE.clear()
        cls._override.disable()
        cls._tmp.cleanup()
        super().tearDownClass()

    def test_prediction_is_returned_with_range_and_version(self):
        result = predict.predict_sales(**valid_inputs())

        self.assertIsInstance(result["value"], float)
        self.assertLess(result["low"], result["value"])
        self.assertLess(result["value"], result["high"])
        self.assertEqual(result["model_version"], self.active_run.version)
        self.assertGreaterEqual(result["typical_error"], 0)

    def test_unseen_item_type_does_not_crash(self):
        # "Snack Foods" never appears in the training frame; the pipeline's
        # OneHotEncoder ignores unknown values instead of failing.
        result = predict.predict_sales(**valid_inputs(item_type="Snack Foods"))
        self.assertIsInstance(result["value"], float)
        self.assertEqual(result["model_version"], self.active_run.version)

    def test_boundaries_of_the_observed_ranges_are_accepted(self):
        for field, low, high in [
            ("weight", predict.WEIGHT_RANGE[0], predict.WEIGHT_RANGE[1]),
            ("visibility", predict.VISIBILITY_RANGE[0], predict.VISIBILITY_RANGE[1]),
            ("establishment_year", predict.YEAR_RANGE[0], predict.YEAR_RANGE[1]),
        ]:
            with self.subTest(field=field):
                result = predict.predict_sales(**valid_inputs(**{field: low}))
                self.assertIn("value", result)
                result = predict.predict_sales(**valid_inputs(**{field: high}))
                self.assertIn("value", result)

    def test_prediction_is_logged(self):
        self.assertEqual(PredictionLog.objects.count(), 0)

        result = predict.predict_sales(**valid_inputs())

        log = PredictionLog.objects.get()
        self.assertEqual(log.model_run, self.active_run)
        self.assertAlmostEqual(log.predicted_value, result["value"])
        self.assertEqual(log.inputs["item_type"], "Dairy")
        self.assertEqual(log.inputs["outlet_type"], "Supermarket Type1")

    def test_invalid_ranges_are_rejected_and_not_logged(self):
        cases = [
            {"weight": 100.0},
            {"weight": 4.0},
            {"visibility": 0.9},
            {"establishment_year": 2005},
            {"establishment_year": 2023},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(InvalidInputError):
                    predict.predict_sales(**valid_inputs(**overrides))
        self.assertEqual(PredictionLog.objects.count(), 0)

    def test_unknown_choice_is_rejected(self):
        with self.assertRaises(InvalidInputError):
            predict.predict_sales(**valid_inputs(outlet_type="Corner Shop"))
        with self.assertRaises(InvalidInputError):
            predict.predict_sales(**valid_inputs(category="Pets"))

    def test_blank_item_type_is_rejected(self):
        with self.assertRaises(InvalidInputError):
            predict.predict_sales(**valid_inputs(item_type="   "))


class PredictWithoutModelTests(TestCase):
    """With no registered model at all, prediction fails loudly, not with a 500."""

    def setUp(self):
        registry._CACHE.clear()

    def test_predict_raises_not_trained(self):
        with self.assertRaises(NotTrainedError):
            predict.predict_sales(**valid_inputs())

    def test_batch_predict_raises_not_trained(self):
        with self.assertRaises(NotTrainedError):
            predict.predict_by_item_type(
                outlet_type="Supermarket Type1",
                location_tier="Tier 1",
                establishment_year=2016,
                sales_frame=make_synthetic_frame(),
            )


class PredictByItemTypeTests(TestCase):
    """The batch function: one prediction per item type for a fixed outlet."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._tmp = tempfile.TemporaryDirectory()
        cls._override = override_settings(ML_ARTIFACTS_DIR=Path(cls._tmp.name))
        cls._override.enable()
        registry._CACHE.clear()
        cls.active_run = register(train(make_synthetic_frame()))

    @classmethod
    def tearDownClass(cls):
        registry._CACHE.clear()
        cls._override.disable()
        cls._tmp.cleanup()
        super().tearDownClass()

    def test_one_row_per_item_type_sorted_descending(self):
        rows = predict.predict_by_item_type(
            outlet_type="Supermarket Type1",
            location_tier="Tier 1",
            establishment_year=2016,
            sales_frame=make_synthetic_frame(),
        )

        self.assertEqual(
            {row["item_type"] for row in rows},
            {"Dairy", "Soft Drinks", "Household"},
        )
        predicted = [row["predicted"] for row in rows]
        self.assertEqual(predicted, sorted(predicted, reverse=True))

    def test_batch_is_not_logged(self):
        before = PredictionLog.objects.count()
        predict.predict_by_item_type(
            outlet_type="Grocery Store",
            location_tier="Tier 2",
            establishment_year=2018,
            sales_frame=make_synthetic_frame(),
        )
        self.assertEqual(PredictionLog.objects.count(), before)

    def test_invalid_profile_is_rejected(self):
        with self.assertRaises(InvalidInputError):
            predict.predict_by_item_type(
                outlet_type="Corner Shop",
                location_tier="Tier 1",
                establishment_year=2016,
            )
        with self.assertRaises(InvalidInputError):
            predict.predict_by_item_type(
                outlet_type="Supermarket Type1",
                location_tier="Tier 1",
                establishment_year=1998,
            )
