"""EVALUATE: R2 / MAE / RMSE, actual-vs-predicted points, feature importances."""

from __future__ import annotations

import numpy as np
from pandas import DataFrame, Series
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error

# How many actual-vs-predicted points land in the chart payload.
SAMPLE_SIZE = 30
# Repeats per feature for permutation importance.
IMPORTANCE_REPEATS = 5
# Residual quantiles reported, e.g. "typical error ±X" comes from the median.
RESIDUAL_QUANTILES = [0.05, 0.25, 0.50, 0.75, 0.95]


def compute_metrics(y_true, y_pred) -> dict[str, float]:
    """The three headline metrics, as plain floats safe to store in JSON."""
    return {
        "r2": float(r2_score(y_true, y_pred)),
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(root_mean_squared_error(y_true, y_pred)),
    }


def build_evaluation(
    pipeline,
    X_test: DataFrame,
    y_test: Series,
    random_state: int = 42,
) -> dict:
    """Build the evaluation payload stored on the ModelRun.

    Everything is computed on the held-out set:
      * actual_vs_predicted - a deterministic sample for the chart
      * residual_quantiles / typical_error - "a typical sale is off by ±X"
      * feature_importances - permutation importance, one entry per original
        column (readable, unlike the one-hot exploded importances)
    """
    y_pred = pipeline.predict(X_test)
    residuals = y_test.to_numpy() - y_pred
    abs_residuals = np.abs(residuals)

    rng = np.random.default_rng(random_state)
    size = min(SAMPLE_SIZE, len(y_test))
    sample_idx = np.sort(rng.choice(len(y_test), size=size, replace=False))
    actual_vs_predicted = [
        {"actual": float(y_test.iloc[i]), "predicted": float(y_pred[pos])}
        for pos, i in enumerate(sample_idx)
    ]

    residual_quantiles = {
        f"q{int(q * 100)}": float(np.quantile(residuals, q)) for q in RESIDUAL_QUANTILES
    }
    typical_error = {
        # Half of all sales are off by less than this, in either direction.
        "median_abs_residual": float(np.median(abs_residuals)),
        "p90_abs_residual": float(np.quantile(abs_residuals, 0.90)),
    }

    perm = permutation_importance(
        pipeline,
        X_test,
        y_test,
        scoring="r2",
        n_repeats=IMPORTANCE_REPEATS,
        random_state=random_state,
    )
    feature_importances = sorted(
        (
            {"feature": name, "importance": float(mean), "std": float(std)}
            for name, mean, std in zip(X_test.columns, perm.importances_mean, perm.importances_std)
        ),
        key=lambda entry: entry["importance"],
        reverse=True,
    )

    return {
        "actual_vs_predicted": actual_vs_predicted,
        "residual_quantiles": residual_quantiles,
        "typical_error": typical_error,
        "feature_importances": feature_importances,
    }
