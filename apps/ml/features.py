"""FEATURES: pull SalesRecords into a DataFrame; one feature definition shared by training and prediction."""

from __future__ import annotations

import pandas as pd
from django.conf import settings

from apps.core.models import SalesRecord

# Categorical columns are one-hot encoded; numeric columns are imputed and scaled.
CATEGORICAL_FEATURES = ["item_type", "fat_content", "category", "outlet_type", "location_tier"]
NUMERIC_FEATURES = ["weight", "visibility", "establishment_year", "outlet_age"]


class FeatureError(Exception):
    """Raised when the sales frame cannot be assembled into features."""


def feature_columns(
    include_rating: bool = False, include_outlet_size: bool = False
) -> tuple[list[str], list[str]]:
    """Return (categorical, numeric) feature column names.

    Switches default to off:
      * rating - not known before a sale happens, so including it would leak
        the answer into a pre-sale prediction.
      * outlet_size - inconsistent for 3 outlets (the same outlet appears with
        different sizes), so it is not trustworthy.
    """
    categorical = list(CATEGORICAL_FEATURES)
    numeric = list(NUMERIC_FEATURES)
    if include_outlet_size:
        categorical.append("outlet_size")
    if include_rating:
        numeric.append("rating")
    return categorical, numeric


def load_sales_frame() -> pd.DataFrame:
    """Flatten SalesRecords into a wide DataFrame with model-ready column names.

    The raw item ID is deliberately NOT a feature: with 1,559 values the model
    would just memorise items instead of learning from their attributes.
    """
    records = (
        SalesRecord.objects.select_related("item", "outlet")
        .values(
            "item__item_id",
            "item__item_type",
            "item__fat_content",
            "item__weight",
            "item__category",
            "outlet__outlet_id",
            "outlet__establishment_year",
            "outlet__location_tier",
            "outlet__outlet_type",
            "outlet_size",
            "visibility",
            "sales",
            "rating",
        )
    )
    df = pd.DataFrame.from_records(records)
    if df.empty:
        return df
    df = df.rename(
        columns={
            "item__item_id": "item_id",
            "item__item_type": "item_type",
            "item__fat_content": "fat_content",
            "item__weight": "weight",
            "item__category": "category",
            "outlet__outlet_id": "outlet_id",
            "outlet__establishment_year": "establishment_year",
            "outlet__location_tier": "location_tier",
            "outlet__outlet_type": "outlet_type",
        }
    )
    # Derived feature: how old the outlet is, relative to the reference year.
    df["outlet_age"] = settings.REFERENCE_YEAR - df["establishment_year"]
    return df


def assemble_features(
    df: pd.DataFrame,
    include_rating: bool = False,
    include_outlet_size: bool = False,
) -> tuple[pd.DataFrame, pd.Series]:
    """Split a sales frame into X (feature DataFrame) and y (the sales target).

    Computes the derived outlet_age column if the frame does not have it yet.
    """
    work = df.copy()
    if "outlet_age" not in work.columns:
        work["outlet_age"] = settings.REFERENCE_YEAR - work["establishment_year"]
    categorical, numeric = feature_columns(include_rating, include_outlet_size)
    columns = categorical + numeric
    missing = [col for col in columns if col not in work.columns]
    if missing:
        raise FeatureError(f"Sales frame is missing feature column(s): {', '.join(missing)}")
    return work[columns], work["sales"]
