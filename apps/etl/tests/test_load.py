"""Tests that the load step is idempotent: loading twice changes nothing."""

from django.test import TestCase
import pandas as pd

from apps.core.models import Item, Outlet, SalesRecord
from apps.etl.load import load


def make_clean_df() -> pd.DataFrame:
    """A cleaned DataFrame in the exact shape transform() produces."""
    return pd.DataFrame(
        {
            "item_id": ["FDX01", "FDX01", "DRX01"],
            "item_type": ["Dairy", "Dairy", "Soft Drinks"],
            "fat_content": ["Low Fat", "Low Fat", "Low Fat"],
            "weight": [5.0, 5.0, 4.0],
            "category": ["Food", "Food", "Drink"],
            "weight_imputed": [False, False, False],
            "outlet_id": ["OUT01", "OUT02", "OUT01"],
            "establishment_year": [2016, 2016, 2020],
            "location_tier": ["Tier 1", "Tier 1", "Tier 3"],
            "outlet_type": [
                "Supermarket Type1",
                "Supermarket Type1",
                "Supermarket Type2",
            ],
            "outlet_size": ["Small", "Small", "High"],
            "visibility": [0.15, 0.10, 0.50],
            "visibility_imputed": [True, False, False],
            "sales": [100.0, 200.0, 600.0],
            "rating": [4.0, 4.0, 5.0],
        }
    )


class LoadTests(TestCase):
    def test_load_creates_expected_rows(self):
        load(make_clean_df())
        self.assertEqual(Outlet.objects.count(), 2)
        self.assertEqual(Item.objects.count(), 2)
        self.assertEqual(SalesRecord.objects.count(), 3)

    def test_loading_twice_keeps_row_counts(self):
        load(make_clean_df())
        load(make_clean_df())
        self.assertEqual(Outlet.objects.count(), 2)
        self.assertEqual(Item.objects.count(), 2)
        self.assertEqual(SalesRecord.objects.count(), 3)

    def test_reload_updates_values_without_duplicates(self):
        df = make_clean_df()
        load(df)
        # Change a value and reload: counts stay, data is refreshed.
        df.loc[df["item_id"] == "FDX01", "weight"] = 6.0
        load(df)
        self.assertEqual(Item.objects.count(), 2)
        self.assertEqual(SalesRecord.objects.count(), 3)
        self.assertEqual(Item.objects.get(item_id="FDX01").weight, 6.0)
