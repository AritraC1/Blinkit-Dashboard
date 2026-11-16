"""EXTRACT: read the raw Blinkit Excel file into a tidy DataFrame."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from django.conf import settings


class ExtractError(Exception):
    """Raised when the raw file cannot be read or is missing columns."""


# The 12 columns the raw workbook must contain, as they appear in the Excel file.
EXPECTED_COLUMNS = [
    "Item Fat Content",
    "Item Identifier",
    "Item Type",
    "Outlet Establishment Year",
    "Outlet Identifier",
    "Outlet Size",
    "Outlet Location Type",
    "Outlet Type",
    "Item Visibility",
    "Item Weight",
    "Sales",
    "Rating",
]

# Canonical snake_case names, keyed by the normalised form of the raw header
# ("Total Sales" and "Sales" both map to `sales`, so a slightly different
# workbook still loads).
_CANONICAL = {
    "item_fat_content": "item_fat_content",
    "item_identifier": "item_identifier",
    "item_type": "item_type",
    "outlet_establishment_year": "outlet_establishment_year",
    "outlet_identifier": "outlet_identifier",
    "outlet_size": "outlet_size",
    "outlet_location_type": "outlet_location_type",
    "outlet_type": "outlet_type",
    "item_visibility": "item_visibility",
    "item_weight": "item_weight",
    "total_sales": "sales",
    "sales": "sales",
    "rating": "rating",
}


def _normalise(name: str) -> str:
    """'  Outlet Establishment Year ' -> 'outlet_establishment_year'."""
    return re.sub(r"\s+", "_", str(name).strip().lower())


def extract(path: str | Path | None = None) -> pd.DataFrame:
    """Read the raw Excel file, trim whitespace and rename to snake_case.

    Returns a raw DataFrame whose columns are the canonical snake_case names.
    Raises ExtractError naming the missing columns if any of the 12 expected
    columns are absent.
    """
    file_path = Path(path or settings.RAW_DATA_PATH)
    if not file_path.exists():
        raise ExtractError(f"Raw data file not found: {file_path}")

    try:
        df = pd.read_excel(file_path)
    except Exception as exc:
        raise ExtractError(f"Could not read {file_path}: {exc}") from exc

    df.columns = [str(col).strip() for col in df.columns]

    found = {_normalise(col) for col in df.columns}
    missing = [
        col for col in EXPECTED_COLUMNS
        if _normalise(col) not in found and not (col == "Sales" and "total_sales" in found)
    ]
    if missing:
        raise ExtractError(
            f"Raw data is missing {len(missing)} expected column(s): "
            + ", ".join(missing)
        )

    rename = {
        col: _CANONICAL[_normalise(col)]
        for col in df.columns
        if _normalise(col) in _CANONICAL
    }
    df = df.rename(columns=rename)

    # Trim stray whitespace from every text column.
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].str.strip()

    return df
