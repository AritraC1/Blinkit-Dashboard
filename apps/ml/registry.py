"""REGISTRY: save/load model artifacts in ml_artifacts/, create ModelRun rows, cache the active model."""

from __future__ import annotations

import re
from pathlib import Path

import joblib
import sklearn
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from sklearn.pipeline import Pipeline

from .models import ModelRun

# Process-level cache so the active pipeline is loaded from disk once.
_CACHE: dict = {"version": None, "run": None, "pipeline": None}


def register(bundle: dict, notes: str = "", activate: bool = True) -> ModelRun:
    """Save the pipeline to disk and record it as a ModelRun, atomically.

    With activate=True the new run becomes the only active model. The bundle
    is what train() returns; only the "pipeline" key is not stored in the
    database - it goes to a joblib file under ML_ARTIFACTS_DIR instead.
    """
    version = _make_version(bundle["algorithm"])
    artifacts_dir = Path(settings.ML_ARTIFACTS_DIR)
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifacts_dir / f"{version}.joblib"
    joblib.dump(bundle["pipeline"], artifact_path)

    with transaction.atomic():
        run = ModelRun.objects.create(
            version=version,
            algorithm=bundle["algorithm"],
            train_size=bundle["train_size"],
            test_size=bundle["test_size"],
            metrics=bundle["metrics"],
            baseline_metrics=bundle["baseline_metrics"],
            feature_list=bundle["feature_list"],
            evaluation=bundle["evaluation"],
            artifact_path=str(artifact_path),
            sklearn_version=bundle.get("sklearn_version", sklearn.__version__),
            notes=notes,
        )
        if activate:
            ModelRun.objects.exclude(pk=run.pk).update(is_active=False)
            ModelRun.objects.filter(pk=run.pk).update(is_active=True)
            run.is_active = True

    # A new active model invalidates anything cached for the old one.
    _CACHE.clear()
    return run


def get_active_run() -> ModelRun | None:
    """The active ModelRun, cached for the lifetime of the process."""
    if _CACHE.get("run") is None:
        run = ModelRun.objects.filter(is_active=True).first()
        if run is None:
            return None
        _CACHE["run"] = run
    return _CACHE["run"]


def load_pipeline() -> Pipeline | None:
    """Load the active pipeline, cached in memory once per process."""
    run = get_active_run()
    if run is None:
        return None
    if _CACHE.get("pipeline") is None or _CACHE.get("version") != run.version:
        _CACHE["pipeline"] = joblib.load(run.artifact_path)
        _CACHE["version"] = run.version
    return _CACHE["pipeline"]


def _make_version(algorithm: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", algorithm.lower()).strip("-")
    stamp = timezone.now().strftime("%Y%m%d-%H%M%S-%f")
    return f"{slug}-{stamp}"
