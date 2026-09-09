"""Load a safe public view of the trained model's metadata file.

The file is produced by the locked training pipeline. This module only reads it
and drops fields that would leak a machine path or environment fingerprint.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.errors import ModelUnavailableError
from app.schemas.model_info import ModelInfoResponse
from app.services.ml_runtime import models_dir
from ml.src import config as ml_config


# Metrics a reviewer can use to judge the locked model. Training-time internals
# (seconds, selection_score internals) stay out of the API.
_PUBLIC_METRIC_KEYS = (
    "accuracy",
    "precision",
    "recall",
    "f1",
    "roc_auc",
    "cv_f1_mean",
    "cv_recall_mean",
    "cv_roc_auc_mean",
)


def get_model_info() -> ModelInfoResponse:
    """Return the public subset of ``model_metadata.json``."""
    directory = Path(models_dir()) if models_dir() else ml_config.MODELS_DIR
    path = directory / ml_config.METADATA_FILENAME
    if not path.exists():
        raise ModelUnavailableError(
            "Model metadata is not available on this server. "
            "Train the model with `python -m ml.src.training.train`."
        )

    raw = json.loads(path.read_text(encoding="utf-8"))
    metrics = raw.get("metrics") or {}
    public_metrics = {
        key: metrics[key] for key in _PUBLIC_METRIC_KEYS if key in metrics
    }
    selection = raw.get("selection_strategy") or {}

    return ModelInfoResponse(
        model_name=str(raw.get("model_name", "unknown")),
        model_version=str(raw.get("model_version", "unknown")),
        target=str(raw.get("target", "Churn")),
        dataset_name=str(raw.get("dataset_name", "IBM Telco Customer Churn")),
        dataset_rows_used=raw.get("dataset_rows_used"),
        feature_count=len(raw.get("features") or []),
        transformed_feature_count=raw.get("transformed_feature_count"),
        training_date=raw.get("training_date"),
        risk_thresholds=raw.get("risk_thresholds") or {},
        metrics=public_metrics,
        class_balance=raw.get("class_balance") or {},
        selection_reason=selection.get("reason"),
    )
