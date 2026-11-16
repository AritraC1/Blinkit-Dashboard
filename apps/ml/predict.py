"""PREDICT: validate inputs, build a one-row DataFrame, call the active model, log a PredictionLog.

Two entry points, both used by the dashboard views:
  * predict_sales - one what-if row, logged as a PredictionLog
  * predict_by_item_type - every item type for one outlet profile (not logged;
    it is chart data, not an audited prediction)
"""

from __future__ import annotations

import pandas as pd
from django.conf import settings
from django.db.models import Avg, Count

from apps.core.models import (
    FatContent,
    Item,
    ItemCategory,
    LocationTier,
    OutletType,
    SalesRecord,
)

from . import registry
from .models import PredictionLog

# Observed ranges in the cleaned dataset. Inputs outside them are rejected:
# the model has never seen such values, so its answer there would be guesswork.
WEIGHT_RANGE = (4.5, 21.4)
VISIBILITY_RANGE = (0.0, 0.33)
YEAR_RANGE = (2011, 2022)

# Choice-backed fields, validated against the model choices.
CHOICE_FIELDS = {
    "category": ItemCategory.values,
    "fat_content": FatContent.values,
    "outlet_type": OutletType.values,
    "location_tier": LocationTier.values,
}

# Used only when the data source gives no visibility at all (pure fallback).
DEFAULT_VISIBILITY = 0.1


class PredictionError(Exception):
    """Base class for prediction failures surfaced to the views."""


class NotTrainedError(PredictionError):
    """Raised when no model has been registered yet."""


class InvalidInputError(PredictionError):
    """Raised when an input is out of range or not an allowed choice."""


def _check_range(name: str, value, bounds: tuple[float, float]) -> float:
    low, high = bounds
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise InvalidInputError(f"{name} must be a number, got {value!r}.")
    if not low <= number <= high:
        raise InvalidInputError(
            f"{name} must be between {low:g} and {high:g}, got {number:g}."
        )
    return number


def _check_choice(name: str, value, allowed) -> str:
    if value not in allowed:
        raise InvalidInputError(
            f"{name} {value!r} is not one of: {', '.join(allowed)}."
        )
    return value


def validate_inputs(inputs: dict) -> dict:
    """Validate one prediction request, or raise InvalidInputError.

    Ranges are the observed dataset ranges; the four choice-backed fields must
    match their model choices. item_type is free text in the source data, so it
    only needs to be non-empty - the pipeline ignores unseen values.
    """
    cleaned: dict = {}
    cleaned["weight"] = _check_range("weight", inputs.get("weight"), WEIGHT_RANGE)
    cleaned["visibility"] = _check_range(
        "visibility", inputs.get("visibility"), VISIBILITY_RANGE
    )
    cleaned["establishment_year"] = int(
        _check_range("establishment_year", inputs.get("establishment_year"), YEAR_RANGE)
    )
    for name, allowed in CHOICE_FIELDS.items():
        cleaned[name] = _check_choice(name, inputs.get(name), allowed)
    item_type = str(inputs.get("item_type") or "").strip()
    if not item_type:
        raise InvalidInputError("item_type is required.")
    cleaned["item_type"] = item_type
    return cleaned


def validate_profile(
    outlet_type, location_tier, establishment_year
) -> dict:
    """Validate an outlet profile (no item attributes involved)."""
    return {
        "outlet_type": _check_choice("outlet_type", outlet_type, CHOICE_FIELDS["outlet_type"]),
        "location_tier": _check_choice(
            "location_tier", location_tier, CHOICE_FIELDS["location_tier"]
        ),
        "establishment_year": int(
            _check_range(
                "establishment_year", establishment_year, YEAR_RANGE
            )
        ),
    }


def _row_frame(row: dict) -> pd.DataFrame:
    """One-row feature frame, with the derived outlet_age added."""
    full = dict(row)
    full["outlet_age"] = settings.REFERENCE_YEAR - full["establishment_year"]
    return pd.DataFrame([full])


def predict_sales(**inputs) -> dict:
    """Validate one what-if request, predict it with the active model, log it.

    Returns the predicted value, a typical-error range (from the held-out
    residual quantiles of the active run) and the model version.
    """
    cleaned = validate_inputs(inputs)

    run = registry.get_active_run()
    if run is None:
        raise NotTrainedError(
            "No model trained yet - run `uv run python manage.py train_model`."
        )
    pipeline = registry.load_pipeline()
    value = float(pipeline.predict(_row_frame(cleaned))[0])

    typical = (run.evaluation or {}).get("typical_error") or {}
    median_error = float(typical.get("median_abs_residual", 0.0))
    p90_error = float(typical.get("p90_abs_residual", median_error))

    PredictionLog.objects.create(
        model_run=run, inputs=cleaned, predicted_value=value
    )

    return {
        "value": value,
        "low": value - median_error,
        "high": value + median_error,
        "typical_error": median_error,
        "p90_error": p90_error,
        "model_version": run.version,
    }


def _representative_items(sales_frame: pd.DataFrame | None = None) -> dict[str, dict]:
    """One representative item per item type.

    Attributes come from the database when it is populated (most common
    fat/category combo, mean weight); an explicitly passed sales frame is the
    fallback so the function also works with a synthetic training frame.
    """
    items: dict[str, dict] = {}
    combos = (
        Item.objects.values("item_type", "fat_content", "category")
        .annotate(n=Count("item_id"), weight=Avg("weight"))
        .order_by("item_type", "-n")
    )
    for combo in combos:
        items.setdefault(
            combo["item_type"],
            {
                "item_type": combo["item_type"],
                "fat_content": combo["fat_content"],
                "category": combo["category"],
                "weight": combo["weight"] or sum(WEIGHT_RANGE) / 2,
            },
        )
    if items or sales_frame is None or sales_frame.empty:
        return items
    grouped = sales_frame.groupby("item_type", sort=False)
    for item_type, group in grouped:
        first = group.iloc[0]
        weights = pd.to_numeric(group["weight"], errors="coerce")
        items[item_type] = {
            "item_type": item_type,
            "fat_content": first["fat_content"],
            "category": first["category"],
            "weight": float(weights.median()) if weights.notna().any() else sum(WEIGHT_RANGE) / 2,
        }
    return items


def _visibility_map(
    sales_frame: pd.DataFrame | None = None,
) -> tuple[dict[str, float], float]:
    """Average visibility per item type, plus an overall fallback value."""
    rows = SalesRecord.objects.values("item__item_type").annotate(v=Avg("visibility"))
    visibility = {row["item__item_type"]: row["v"] for row in rows}
    overall = SalesRecord.objects.aggregate(v=Avg("visibility"))["v"]
    if overall is None and sales_frame is not None and not sales_frame.empty:
        grouped = sales_frame.groupby("item_type")["visibility"]
        visibility = {key: float(value) for key, value in grouped.median().items()}
        overall = float(sales_frame["visibility"].median())
    fallback = float(overall) if overall is not None else DEFAULT_VISIBILITY
    return visibility, fallback


def predict_by_item_type(
    *, outlet_type, location_tier, establishment_year, sales_frame: pd.DataFrame | None = None
) -> list[dict]:
    """Predict every known item type for one fixed outlet profile, in one batch.

    Each item type is represented by its typical attributes (mean weight, most
    common fat/category combo, average visibility). Returns rows sorted by
    predicted sales, highest first; these are chart/table data, so they are not
    written to the PredictionLog.
    """
    profile = validate_profile(outlet_type, location_tier, establishment_year)

    if registry.get_active_run() is None:
        raise NotTrainedError(
            "No model trained yet - run `uv run python manage.py train_model`."
        )
    pipeline = registry.load_pipeline()

    items = _representative_items(sales_frame)
    if not items:
        return []
    visibility_map, fallback_visibility = _visibility_map(sales_frame)

    rows = []
    for item_type, attributes in items.items():
        rows.append(
            {
                **profile,
                **attributes,
                "visibility": visibility_map.get(item_type, fallback_visibility),
                "outlet_age": settings.REFERENCE_YEAR - profile["establishment_year"],
            }
        )

    values = pipeline.predict(pd.DataFrame(rows))
    predictions = [
        {"item_type": row["item_type"], "predicted": float(value)}
        for row, value in zip(rows, values)
    ]
    predictions.sort(key=lambda entry: entry["predicted"], reverse=True)
    return predictions
