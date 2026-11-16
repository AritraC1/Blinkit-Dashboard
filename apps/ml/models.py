"""Registry tables: one row per trained model, plus a log of every prediction."""

from __future__ import annotations

from django.db import models


class ModelRun(models.Model):
    """A single trained pipeline and everything needed to audit it."""

    version = models.CharField(max_length=100, unique=True)
    algorithm = models.CharField(max_length=50)
    trained_at = models.DateTimeField(auto_now_add=True)
    train_size = models.PositiveIntegerField()
    test_size = models.PositiveIntegerField()
    # Held-out metrics for the model, e.g. {"r2": 0.14, "mae": 180.2, "rmse": 250.9}
    metrics = models.JSONField()
    # Held-out metrics for the mean-only baseline, same keys.
    baseline_metrics = models.JSONField()
    # Ordered feature column names used by this run.
    feature_list = models.JSONField()
    # Chart data: actual-vs-predicted sample, residual quantiles, permutation importances.
    evaluation = models.JSONField()
    # Where the joblib pipeline lives, e.g. ml_artifacts/gradient-boosting-...joblib
    artifact_path = models.CharField(max_length=500)
    sklearn_version = models.CharField(max_length=50)
    is_active = models.BooleanField(default=False, db_index=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-trained_at"]

    def __str__(self) -> str:
        active = " (active)" if self.is_active else ""
        return f"{self.version}{active}"


class PredictionLog(models.Model):
    """One row per prediction served, for auditing the active model."""

    model_run = models.ForeignKey(
        ModelRun, on_delete=models.CASCADE, related_name="prediction_logs"
    )
    inputs = models.JSONField()
    predicted_value = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.predicted_value:.1f} @ {self.created_at:%Y-%m-%d %H:%M} ({self.model_run.version})"
