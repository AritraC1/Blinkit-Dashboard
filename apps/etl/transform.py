"""TRANSFORM: clean the raw DataFrame into load-ready records.

Rules, applied in order:

1. Fat content: five spellings ("Low Fat", "low fat", "LF", "Regular", "reg")
   collapse to Low Fat / Regular. Items whose identifier starts with "NC"
   (non-consumables) become "Non-Edible" - "low fat" is meaningless on
   household goods.
2. Weight: nulls are filled from the same item's other rows (weight is
   constant per item). Items with no weight anywhere fall back to the median
   weight of their item type.
3. Visibility: zeros become missing, then are filled from the item's mean
   visibility across outlets (a global mean is the last-resort fallback).
4. weight_imputed / visibility_imputed flags record every filled value.
5. Item category is derived from the identifier prefix: FD -> Food,
   NC -> Non-Consumable, DR -> Drink.

Returns a (clean DataFrame, imputed counts) tuple.
"""

from __future__ import annotations

import pandas as pd

FAT_MAP = {
    "low fat": "Low Fat",
    "lf": "Low Fat",
    "regular": "Regular",
    "reg": "Regular",
}

CATEGORY_MAP = {
    "FD": "Food",
    "NC": "Non-Consumable",
    "DR": "Drink",
}

NON_EDIBLE = "Non-Edible"


def transform(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """Clean the raw extract. Returns (clean_df, counts per imputation rule)."""
    out = df.copy()
    imputed: dict[str, int] = {}

    # ---- 1. Fat content -----------------------------------------------------
    normalised = out["item_fat_content"].astype("string").str.strip().str.lower()
    out["fat_content"] = normalised.map(FAT_MAP)
    # Non-consumables (household goods etc.): the mapped fat value is
    # meaningless, so label them Non-Edible instead.
    is_non_edible = out["item_identifier"].str.upper().str.startswith("NC")
    out.loc[is_non_edible, "fat_content"] = NON_EDIBLE
    imputed["fat_content_normalised"] = int(normalised.notna().sum())
    imputed["fat_content_non_edible"] = int(is_non_edible.sum())

    # ---- 2. Weight ----------------------------------------------------------
    weight = pd.to_numeric(out["item_weight"], errors="coerce")
    weight_missing = weight.isna()

    # Weight is constant per item: the item's median (over its non-null rows)
    # is that weight.
    item_weight = weight.groupby(out["item_identifier"]).transform("median")
    # Items with no weight anywhere fall back to the median of their item type.
    type_weight = weight.groupby(out["item_type"]).transform("median")

    out["weight"] = weight.fillna(item_weight).fillna(type_weight)
    imputed["weight_filled_from_item"] = int(
        (weight_missing & item_weight.notna()).sum()
    )
    imputed["weight_filled_from_type_median"] = int(
        (weight_missing & item_weight.isna() & type_weight.notna()).sum()
    )
    imputed["weight_imputed_total"] = int(weight_missing.sum())
    out["weight_imputed"] = weight_missing

    # ---- 3. Visibility ------------------------------------------------------
    visibility = pd.to_numeric(out["item_visibility"], errors="coerce")
    zero = visibility == 0
    visibility = visibility.mask(zero)  # zeros are missing, not real values

    # Fill from the item's mean across outlets; global mean as last resort.
    item_visibility = visibility.groupby(out["item_identifier"]).transform("mean")
    global_visibility = visibility.mean()

    out["visibility"] = (
        visibility.fillna(item_visibility).fillna(global_visibility)
    )
    imputed["visibility_zeroed"] = int(zero.sum())
    imputed["visibility_filled_from_item_mean"] = int(
        (zero & item_visibility.notna()).sum()
    )
    imputed["visibility_filled_from_global_mean"] = int(
        (zero & item_visibility.isna() & pd.notna(global_visibility)).sum()
    )
    imputed["visibility_imputed_total"] = int(zero.sum())
    out["visibility_imputed"] = zero

    # ---- 4. (flags set above) -----------------------------------------------

    # ---- 5. Item category from the ID prefix --------------------------------
    prefix = out["item_identifier"].str[:2].str.upper()
    out["category"] = prefix.map(CATEGORY_MAP)
    imputed["category_unknown_prefix"] = int(
        (prefix.notna() & out["category"].isna()).sum()
    )

    # ---- Final column layout ------------------------------------------------
    out["item_id"] = out["item_identifier"]
    out["outlet_id"] = out["outlet_identifier"]
    out["establishment_year"] = pd.to_numeric(
        out["outlet_establishment_year"], errors="coerce"
    ).astype("Int64")
    out["location_tier"] = out["outlet_location_type"]
    out["sales"] = pd.to_numeric(out["sales"], errors="coerce")
    out["rating"] = pd.to_numeric(out["rating"], errors="coerce")

    clean = out[
        [
            # item fields
            "item_id",
            "item_type",
            "fat_content",
            "weight",
            "category",
            "weight_imputed",
            # outlet fields
            "outlet_id",
            "establishment_year",
            "location_tier",
            "outlet_type",
            "outlet_size",
            # sale fields
            "visibility",
            "visibility_imputed",
            "sales",
            "rating",
        ]
    ]

    return clean, imputed
