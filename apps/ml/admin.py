from django.contrib import admin

from .models import ModelRun, PredictionLog


@admin.register(ModelRun)
class ModelRunAdmin(admin.ModelAdmin):
    list_display = ("version", "algorithm", "trained_at", "train_size", "test_size", "is_active")
    list_filter = ("algorithm", "is_active")
    search_fields = ("version", "notes")
    readonly_fields = (
        "version",
        "algorithm",
        "trained_at",
        "train_size",
        "test_size",
        "metrics",
        "baseline_metrics",
        "feature_list",
        "evaluation",
        "artifact_path",
        "sklearn_version",
    )


@admin.register(PredictionLog)
class PredictionLogAdmin(admin.ModelAdmin):
    list_display = ("model_run", "predicted_value", "created_at")
    list_filter = ("model_run",)
    readonly_fields = ("model_run", "inputs", "predicted_value", "created_at")
