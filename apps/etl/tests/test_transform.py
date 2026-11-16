"""Tests for the transform rules, using a tiny hand-made DataFrame."""

from django.test import SimpleTestCase
import pandas as pd

from apps.etl.transform import transform


def make_raw_df() -> pd.DataFrame:
    """Six rows covering every transform rule.

    FDX01: weight known on 2 of 3 rows, one zero visibility.
    NCX01: no weight anywhere (must fall back to item-type median);
           raw fat value is "reg" but becomes Non-Edible.
    NCX02: same item type as NCX01, gives the median; NC -> Non-Edible.
    DRX01: plain Low Fat drink.
    """
    return pd.DataFrame(
        {
            "item_fat_content": ["LF", "Low Fat", "low fat", "reg", "Regular", "Low Fat"],
            "item_identifier": ["FDX01", "FDX01", "FDX01", "NCX01", "NCX02", "DRX01"],
            "item_type": [
                "Dairy",
                "Dairy",
                "Dairy",
                "Household",
                "Household",
                "Soft Drinks",
            ],
            "outlet_establishment_year": [2016, 2016, 2016, 2018, 2018, 2020],
            "outlet_identifier": ["OUT01", "OUT02", "OUT03", "OUT01", "OUT02", "OUT01"],
            "outlet_size": ["Small", "Small", "Small", "Medium", "Medium", "High"],
            "outlet_location_type": ["Tier 1", "Tier 1", "Tier 1", "Tier 2", "Tier 2", "Tier 3"],
            "outlet_type": [
                "Supermarket Type1",
                "Supermarket Type1",
                "Supermarket Type1",
                "Grocery Store",
                "Grocery Store",
                "Supermarket Type2",
            ],
            "item_visibility": [0.0, 0.10, 0.20, 0.30, 0.40, 0.50],
            "item_weight": [None, 5.0, 5.0, None, 8.0, 4.0],
            "sales": [100.0, 200.0, 300.0, 400.0, 500.0, 600.0],
            "rating": [4.0, 4.0, 5.0, 3.0, 4.0, 5.0],
        }
    )


class TransformTests(SimpleTestCase):
    def setUp(self):
        self.clean, self.imputed = transform(make_raw_df())

    def test_fat_content_mapping(self):
        # All five raw spellings collapse to the two canonical values...
        by_item = self.clean.set_index("item_id")["fat_content"]
        self.assertEqual(by_item.loc["FDX01"].unique().tolist(), ["Low Fat"])
        self.assertEqual(by_item.loc["DRX01"], "Low Fat")
        # ...but NC items become Non-Edible regardless of the raw value.
        self.assertEqual(by_item.loc["NCX01"], "Non-Edible")
        self.assertEqual(by_item.loc["NCX02"], "Non-Edible")

    def test_weight_filled_from_same_item(self):
        # FDX01 has weight 5.0 on two rows; the null row inherits it.
        fdx = self.clean[self.clean["item_id"] == "FDX01"]
        self.assertTrue((fdx["weight"] == 5.0).all())
        # Only the originally-null row is flagged.
        self.assertEqual(fdx["weight_imputed"].sum(), 1)
        null_row = fdx[fdx["weight_imputed"]]
        self.assertEqual(null_row["weight"].iloc[0], 5.0)
        # Rows that already had a weight are untouched.
        self.assertFalse(fdx.loc[~fdx["weight_imputed"], "weight_imputed"].any())

    def test_weight_falls_back_to_item_type_median(self):
        # NCX01 has no weight anywhere; Household's only other weight is 8.0.
        ncx01 = self.clean[self.clean["item_id"] == "NCX01"].iloc[0]
        self.assertEqual(ncx01["weight"], 8.0)
        self.assertTrue(ncx01["weight_imputed"])
        self.assertEqual(
            self.imputed["weight_filled_from_type_median"], 1,
        )

    def test_zero_visibility_filled_from_item_mean(self):
        # FDX01's other visibilities are 0.10 and 0.20, so the zero gets 0.15.
        fdx = self.clean[self.clean["item_id"] == "FDX01"]
        zero_row = fdx[fdx["visibility_imputed"]]
        self.assertAlmostEqual(zero_row["visibility"].iloc[0], 0.15)
        self.assertEqual(len(zero_row), 1)
        # Non-zero visibilities are untouched and unflagged.
        others = fdx[~fdx["visibility_imputed"]]["visibility"].tolist()
        self.assertEqual(sorted(others), [0.10, 0.20])

    def test_category_derived_from_prefix(self):
        by_item = self.clean.drop_duplicates("item_id").set_index("item_id")["category"]
        self.assertEqual(by_item.loc["FDX01"], "Food")
        self.assertEqual(by_item.loc["NCX01"], "Non-Consumable")
        self.assertEqual(by_item.loc["DRX01"], "Drink")

    def test_no_nulls_in_output(self):
        self.assertFalse(self.clean.drop(columns=["weight_imputed", "visibility_imputed"]).isna().any().any())
