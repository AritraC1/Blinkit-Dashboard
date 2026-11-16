"""PIPELINE: the single entry point chaining extract -> transform -> validate -> load."""

from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings

from .extract import ExtractError, extract
from .load import load
from .transform import transform
from .validate import validate

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """Raised when validation fails and the run cannot continue."""


def run(
    path: str | Path | None = None,
    dry_run: bool = False,
    write_csv: bool = True,
) -> dict:
    """Run the full ETL and return a summary dict.

    Rows are counted and logged at every step. If validation reports errors a
    PipelineError is raised; warnings are included in the summary.
    """
    # ---- EXTRACT ------------------------------------------------------------
    raw = extract(path)
    rows_read = len(raw)
    logger.info("Extracted %d rows from raw data", rows_read)

    # ---- TRANSFORM ----------------------------------------------------------
    clean, imputed = transform(raw)
    logger.info("Transformed %d rows (%d columns)", len(clean), clean.shape[1])
    for rule, count in imputed.items():
        logger.info("Transform: %s = %d", rule, count)

    # ---- VALIDATE -----------------------------------------------------------
    report = validate(clean)
    for warning in report.warnings:
        logger.warning("Validation warning: %s", warning)
    if not report.ok:
        for error in report.errors:
            logger.error("Validation error: %s", error)
        raise PipelineError(
            "Validation failed with "
            f"{len(report.errors)} error(s): " + " | ".join(report.errors)
        )

    summary: dict = {
        "rows_read": rows_read,
        **imputed,
        "warnings": report.warnings,
        "rows_loaded": 0,
    }

    if dry_run:
        logger.info("Dry run: stopping before load")
        return summary

    # ---- LOAD ---------------------------------------------------------------
    summary["rows_loaded"] = load(clean)
    logger.info("Loaded %d SalesRecords", summary["rows_loaded"])

    if write_csv:
        csv_path = _write_cleaned_csv(clean)
        logger.info("Cleaned data written to %s", csv_path)
        summary["csv_path"] = str(csv_path)

    return summary


def _write_cleaned_csv(clean) -> Path:
    processed_dir = Path(settings.PROCESSED_DATA_DIR)
    processed_dir.mkdir(parents=True, exist_ok=True)
    csv_path = processed_dir / "cleaned_sales.csv"
    clean.to_csv(csv_path, index=False)
    return csv_path
