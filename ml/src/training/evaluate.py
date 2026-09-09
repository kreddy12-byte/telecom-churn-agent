"""Model evaluation, cross-validation, and comparison reporting."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_validate

from ml.src import config
from ml.src.logging_config import get_logger

logger = get_logger(__name__)

COMPARISON_COLUMNS: tuple[str, ...] = (
    "model_name",
    "accuracy",
    "precision",
    "recall",
    "f1",
    "roc_auc",
    "cv_f1_mean",
    "cv_f1_std",
    "cv_recall_mean",
    "cv_roc_auc_mean",
    "selection_score",
    "train_time_seconds",
    "inference_time_seconds",
    "true_negatives",
    "false_positives",
    "false_negatives",
    "true_positives",
)


@dataclass
class ModelEvaluation:
    """Metrics for one trained candidate model."""

    model_name: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    confusion_matrix: dict[str, int]
    train_time_seconds: float
    inference_time_seconds: float
    cv_f1_mean: float | None = None
    cv_f1_std: float | None = None
    cv_recall_mean: float | None = None
    cv_roc_auc_mean: float | None = None
    selection_score: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_row(self) -> dict[str, Any]:
        """Flatten into a single row for the comparison table."""
        row = {
            "model_name": self.model_name,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "roc_auc": self.roc_auc,
            "cv_f1_mean": self.cv_f1_mean,
            "cv_f1_std": self.cv_f1_std,
            "cv_recall_mean": self.cv_recall_mean,
            "cv_roc_auc_mean": self.cv_roc_auc_mean,
            "selection_score": self.selection_score,
            "train_time_seconds": self.train_time_seconds,
            "inference_time_seconds": self.inference_time_seconds,
        }
        row.update(self.confusion_matrix)
        return row


def _predicted_probabilities(model: Any, features: pd.DataFrame) -> np.ndarray:
    """Return positive-class scores, falling back to decision_function."""
    if hasattr(model, "predict_proba"):
        return np.asarray(model.predict_proba(features))[:, 1]
    if hasattr(model, "decision_function"):
        scores = np.asarray(model.decision_function(features))
        return 1.0 / (1.0 + np.exp(-scores))
    raise AttributeError(
        f"{type(model).__name__} exposes neither predict_proba nor decision_function; "
        "ROC AUC cannot be computed."
    )


def evaluate_model(
    model_name: str,
    fitted_model: Any,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    train_time_seconds: float,
) -> ModelEvaluation:
    """Score a fitted model on the held-out test set."""
    start = time.perf_counter()
    predictions = fitted_model.predict(x_test)
    inference_time = time.perf_counter() - start

    probabilities = _predicted_probabilities(fitted_model, x_test)
    matrix = confusion_matrix(y_test, predictions, labels=[0, 1])
    true_negatives, false_positives, false_negatives, true_positives = matrix.ravel()

    return ModelEvaluation(
        model_name=model_name,
        accuracy=float(accuracy_score(y_test, predictions)),
        precision=float(precision_score(y_test, predictions, pos_label=1, zero_division=0)),
        recall=float(recall_score(y_test, predictions, pos_label=1, zero_division=0)),
        f1=float(f1_score(y_test, predictions, pos_label=1, zero_division=0)),
        roc_auc=float(roc_auc_score(y_test, probabilities)),
        confusion_matrix={
            "true_negatives": int(true_negatives),
            "false_positives": int(false_positives),
            "false_negatives": int(false_negatives),
            "true_positives": int(true_positives),
        },
        train_time_seconds=round(float(train_time_seconds), 4),
        inference_time_seconds=round(float(inference_time), 4),
    )


def cross_validate_pipeline(
    pipeline: Any,
    x_train: pd.DataFrame,
    y_train: pd.Series,
    folds: int = config.CV_FOLDS,
) -> dict[str, float]:
    """Stratified cross-validation on the training split only.

    These scores drive model selection, which is why they must never see the
    test set. The preprocessor is inside the pipeline, so it is refitted per
    fold and no information leaks across folds either.
    """
    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=config.RANDOM_STATE)
    scores = cross_validate(
        pipeline,
        x_train,
        y_train,
        cv=splitter,
        scoring=("f1", "recall", "roc_auc"),
        n_jobs=None,
        error_score="raise",
    )
    return {
        "cv_f1_mean": float(np.mean(scores["test_f1"])),
        "cv_f1_std": float(np.std(scores["test_f1"])),
        "cv_recall_mean": float(np.mean(scores["test_recall"])),
        "cv_roc_auc_mean": float(np.mean(scores["test_roc_auc"])),
    }


def results_to_dataframe(results: list[ModelEvaluation]) -> pd.DataFrame:
    """Build the comparison table, best model first."""
    frame = pd.DataFrame([result.to_row() for result in results])
    ordered = [column for column in COMPARISON_COLUMNS if column in frame.columns]
    frame = frame[ordered]
    sort_key = "selection_score" if frame["selection_score"].notna().any() else "f1"
    return frame.sort_values(sort_key, ascending=False).reset_index(drop=True)


def save_comparison_reports(
    results: list[ModelEvaluation],
    models_dir: Path | None = None,
    extra: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    """Write ``model_comparison.csv`` and ``model_comparison.json``."""
    target_dir = Path(models_dir) if models_dir else config.MODELS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    frame = results_to_dataframe(results)
    csv_path = target_dir / config.COMPARISON_CSV_FILENAME
    frame.to_csv(csv_path, index=False)

    payload: dict[str, Any] = {
        "dataset": config.DATASET_NAME,
        "random_state": config.RANDOM_STATE,
        "test_size": config.TEST_SIZE,
        "cv_folds": config.CV_FOLDS,
        "selection_weights": config.SELECTION_WEIGHTS,
        "models": [result.to_dict() for result in results],
    }
    if extra:
        payload.update(extra)

    json_path = target_dir / config.COMPARISON_JSON_FILENAME
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    logger.info("Comparison written to %s and %s", csv_path, json_path)
    return csv_path, json_path


def log_comparison(results: list[ModelEvaluation]) -> None:
    """Log the comparison table in a readable form."""
    frame = results_to_dataframe(results)
    display_columns = [
        "model_name",
        "accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "cv_f1_mean",
        "cv_recall_mean",
        "selection_score",
    ]
    logger.info(
        "Model comparison:\n%s",
        frame[display_columns].to_string(index=False, float_format=lambda value: f"{value:.4f}"),
    )
