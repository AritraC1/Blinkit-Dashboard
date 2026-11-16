"""VALIDATE: block bad data, surface known quirks instead of hiding them."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

# Columns the cleaned DataFrame must contain, with the fields that must never
# be null.
REQUIRED_COLUMNS = [
    "item_id",
    "item_type",
    "fat_content",
    "weight",
    "category",
    "weight_imputed",
    "outlet_id",
    "establishment_year",
    "location_tier",
    "outlet_type",
    "outlet_size",
    "visibility",
    "visibility_imputed",
    "sales",
    "rating",
]

NOT_NULL_COLUMNS = [
    "item_id",
    "item_type",
    "fat_content",
    "weight",
    "category",
    "outlet_id",
    "establishment_year",
    "location_tier",
    "outlet_type",
    "outlet_size",
    "visibility",
    "sales",
    "rating",
]


@dataclass
class ValidationReport:
    """Result of validating the cleaned DataFrame."""

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def validate(df: pd.DataFrame) -> ValidationReport:
    """Check the cleaned DataFrame. Errors stop the run; warnings do not.

    Errors:
      * required columns missing
      * duplicate item/outlet pairs
      * leftover nulls in any non-nullable field
      * sales <= 0
      * rating outside 1..5

    Warnings:
      * outlets appearing with more than one outlet size
    """
    errors: list[str] = []
    warnings: list[str] = []

    missing_columns = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing_columns:
        errors.append(
            f"Cleaned data is missing {len(missing_columns)} required column(s): "
            + ", ".join(missing_columns)
        )
        return ValidationReport(errors, warnings)

    duplicates = df.duplicated(subset=["item_id", "outlet_id"])
    if duplicates.any():
        sample = df.loc[duplicates, ["item_id", "outlet_id"]].head(5).values.tolist()
        errors.append(
            f"{int(duplicates.sum())} duplicate item/outlet pair(s), e.g. {sample}"
        )

    for col in NOT_NULL_COLUMNS:
        nulls = df[col].isna().sum()
        if nulls:
            errors.append(f"{int(nulls)} null value(s) left in '{col}'")

    bad_sales = df["sales"] <= 0
    if bad_sales.any():
        errors.append(
            f"{int(bad_sales.sum())} row(s) with sales <= 0, e.g. "
            f"{df.loc[bad_sales, 'sales'].head(5).tolist()}"
        )

    bad_rating = ~df["rating"].between(1, 5)
    if bad_rating.any():
        errors.append(
            f"{int(bad_rating.sum())} row(s) with rating outside 1..5, e.g. "
            f"{df.loc[bad_rating, 'rating'].head(5).tolist()}"
        )

    sizes_per_outlet = df.groupby("outlet_id")["outlet_size"].nunique()
    multi_size = sizes_per_outlet[sizes_per_outlet > 1]
    if not multi_size.empty:
        warnings.append(
            f"{len(multi_size)} outlet(s) appear with more than one size: "
            f"{multi_size.index.tolist()}"
        )

    return ValidationReport(errors, warnings)
