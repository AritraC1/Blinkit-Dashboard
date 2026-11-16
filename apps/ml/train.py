"""TRAIN: build sklearn pipeline; compare mean baseline vs linear vs gradient boosting; keep the best."""

from __future__ import annotations

from typing import Callable

import numpy as np
import sklearn
from pandas import DataFrame, Series
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, cross_validate
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from . import features
from .evaluate import build_evaluation, compute_metrics

RANDOM_STATE = 42
TEST_SIZE = 0.20
CV_SPLITS = 5

# Candidates compared against the mean-only baseline. Everything is wrapped in
# a factory so each candidate gets a fresh estimator for the final refit.
CANDIDATES: dict[str, Callable[[], object]] = {
    "Ridge": lambda: Ridge(alpha=1.0),
    "Random Forest": lambda: RandomForestRegressor(
        n_estimators=300,
        min_samples_leaf=5,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    ),
    "Gradient Boosting": lambda: GradientBoostingRegressor(random_state=RANDOM_STATE),
}


class TrainingError(Exception):
    """Raised when the data cannot support a fair grouped comparison."""


def build_pipeline(model, categorical: list[str], numeric: list[str]) -> Pipeline:
    """One-hot categoricals (ignore unseen values), impute + scale numerics, then the model."""
    preprocessing = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical),
            (
                "numeric",
                Pipeline(
                    [("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]
                ),
                numeric,
            ),
        ]
    )
    return Pipeline([("preprocess", preprocessing), ("model", model)])


def train(
    df: DataFrame | None = None,
    include_rating: bool = False,
    include_outlet_size: bool = False,
    random_state: int = RANDOM_STATE,
) -> dict:
    """Compare candidates with grouped cross-validation and return the winning bundle.

    Splits and CV are grouped by item ID: weight is item-specific, so a random
    split would let the trees recognise items across the split and inflate
    every score. The best candidate is evaluated on the held-out set and then
    refit on all data for the final artifact.

    The bundle contains the registered facts plus the refit pipeline under
    "pipeline"; the registry turns the rest into a ModelRun row.
    """
    if df is None:
        df = features.load_sales_frame()

    X, y = features.assemble_features(df, include_rating, include_outlet_size)
    groups = df["item_id"]
    n_groups = int(groups.nunique())
    if n_groups < 2:
        raise TrainingError(
            f"Need at least 2 distinct items for a grouped split, found {n_groups}."
        )

    # ---- Split: hold out whole items ---------------------------------------
    splitter = GroupShuffleSplit(n_splits=1, test_size=TEST_SIZE, random_state=random_state)
    train_idx, test_idx = next(splitter.split(X, y, groups))
    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]
    groups_train = groups.iloc[train_idx]

    categorical, numeric = features.feature_columns(include_rating, include_outlet_size)
    n_splits = min(CV_SPLITS, int(groups_train.nunique()))
    cv = GroupKFold(n_splits=n_splits)
    scoring = {
        "r2": "r2",
        "mae": "neg_mean_absolute_error",
        "rmse": "neg_root_mean_squared_error",
    }

    # ---- Cross-validate: baseline first, then the candidates ----------------
    cv_results: dict[str, dict[str, float]] = {}
    baseline = build_pipeline(DummyRegressor(strategy="mean"), categorical, numeric)
    cv_results["Mean baseline"] = _summarise(
        cross_validate(baseline, X_train, y_train, groups=groups_train, cv=cv, scoring=scoring)
    )
    for name, factory in CANDIDATES.items():
        candidate = build_pipeline(factory(), categorical, numeric)
        cv_results[name] = _summarise(
            cross_validate(candidate, X_train, y_train, groups=groups_train, cv=cv, scoring=scoring)
        )

    # Pick the best real candidate by CV R2 (never the Dummy - it is only there
    # to show what "no model" scores).
    best_name = max(CANDIDATES, key=lambda name: cv_results[name]["r2"])

    # ---- Evaluate the winner on the held-out items ---------------------------
    best_holdout = build_pipeline(CANDIDATES[best_name](), categorical, numeric)
    best_holdout.fit(X_train, y_train)
    metrics = compute_metrics(y_test, best_holdout.predict(X_test))

    baseline_holdout = build_pipeline(DummyRegressor(strategy="mean"), categorical, numeric)
    baseline_holdout.fit(X_train, y_train)
    baseline_metrics = compute_metrics(y_test, baseline_holdout.predict(X_test))

    evaluation = build_evaluation(best_holdout, X_test, y_test, random_state=random_state)

    # ---- Refit the winner on all data for the deployable artifact -----------
    final_pipeline = build_pipeline(CANDIDATES[best_name](), categorical, numeric)
    final_pipeline.fit(X, y)

    return {
        "pipeline": final_pipeline,
        "algorithm": best_name,
        "feature_list": list(X.columns),
        "train_size": int(len(X_train)),
        "test_size": int(len(X_test)),
        "metrics": metrics,
        "baseline_metrics": baseline_metrics,
        "evaluation": evaluation,
        "cv_results": cv_results,
        "sklearn_version": sklearn.__version__,
    }


def _summarise(scores: dict) -> dict[str, float]:
    """Turn cross_validate output into {r2, mae, rmse} means."""
    return {
        "r2": float(np.mean(scores["test_r2"])),
        "mae": float(-np.mean(scores["test_mae"])),
        "rmse": float(-np.mean(scores["test_rmse"])),
    }
