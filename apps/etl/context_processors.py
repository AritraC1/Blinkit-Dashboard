"""Context processors shared by every template."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from django.conf import settings


def etl_info(request):
    """Data source and last ETL run date for the site footer.

    The ETL command writes the cleaned dataset to
    ``settings.PROCESSED_DATA_DIR / "cleaned_sales.csv``; that file's
    modification time is used as the last ETL date. If it does not exist,
    ``run_etl`` has not been run yet.
    """
    data_source = getattr(settings, "RAW_DATA_PATH", None)
    processed_dir = getattr(settings, "PROCESSED_DATA_DIR", None)

    last_run = None
    if processed_dir:
        csv_path = Path(processed_dir) / "cleaned_sales.csv"
        if csv_path.exists():
            last_run = datetime.fromtimestamp(csv_path.stat().st_mtime)

    return {
        "etl_data_source": data_source.name if data_source else "BlinkIT_Grocery_Data.xlsx",
        "etl_last_run": last_run,
    }
