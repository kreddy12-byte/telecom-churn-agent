"""End-to-end training entrypoint.

Run as a module from the repository root::

    python -m ml.src.training.train

Steps: acquire -> validate -> clean -> split -> preprocess -> train candidates ->
evaluate -> select -> persist artifacts.
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import sklearn
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from ml.src import config
from ml.src.data.clean_dataset import clean_dataset
from ml.src.data.download_dataset import ensure_dataset
from ml.src.data.validate_dataset import load_raw_dataset, log_dataset_summary, validate_dataset
from ml.src.exceptions import (
    DatasetDownloadError,
    DatasetNotFoundError,
    DatasetValidationError,
    MLPipelineError,
)
from ml.src.logging_config import configure_logging, get_logger
from ml.src.preprocessing.pipeline import (
    build_preprocessor,
    get_transformed_feature_names,
    resolve_feature_types,
    split_features_target,
)
from ml.src.training.evaluate import (
    ModelEvaluation,
    cross_validate_pipeline,
    evaluate_model,
    log_comparison,
    results_to_dataframe,
    save_comparison_reports,
)
from ml.src.training.model_selection import (
    XGBOOST_AVAILABLE,
    ModelSelection,
    compute_scale_pos_weight,
    get_candidate_models,
    models_without_class_weighting,
    select_best_model,
)

logger = get_logger(__name__)

PREPROCESSOR_STEP = "preprocessor"
MODEL_STEP = "model"


@dataclass
class TrainingArtifacts:
    """Paths and summary produced by a training run."""

    best_model_path: Path
    preprocessor_path: Path
    metadata_path: Path
    comparison_csv_path: Path
    comparison_json_path: Path
    selection: ModelSelection
    results: list[ModelEvaluation]


def describe_class_balance(target: pd.Series) -> dict[str, Any]:
    """Summarise the class distribution and imbalance ratio."""
    counts = target.value_counts().to_dict()
    negatives = int(counts.get(0, 0))
    positives = int(counts.get(1, 0))
    total = negatives + positives or 1
    return {
        "negative_count": negatives,
        "positive_count": positives,
        "positive_rate": round(positives / total, 4),
        "imbalance_ratio_negative_to_positive": round(negatives / positives, 4) if positives else None,
    }


def train_single_model(
    name: str,
    estimator: Any,
    numeric_features: list[str],
    categorical_features: list[str],
    x_train: pd.DataFrame,
    y_train: pd.Series,
    x_test: pd.DataFrame,
    y_test: pd.Series,
    run_cv: bool = True,
) -> tuple[Pipeline, ModelEvaluation]:
    """Fit one candidate pipeline and evaluate it on the held-out test set."""
    pipeline = Pipeline(
        steps=[
            (PREPROCESSOR_STEP, build_preprocessor(numeric_features, categorical_features)),
            (MODEL_STEP, estimator),
        ]
    )

    cv_scores: dict[str, float] = {}
    if run_cv:
        logger.info("[%s] cross-validating on the training split", name)
        cv_scores = cross_validate_pipeline(pipeline, x_train, y_train)

    logger.info("[%s] fitting on the full training split", name)
    start = time.perf_counter()
    pipeline.fit(x_train, y_train)
    train_time = time.perf_counter() - start

    evaluation = evaluate_model(name, pipeline, x_test, y_test, train_time)
    evaluation.cv_f1_mean = cv_scores.get("cv_f1_mean")
    evaluation.cv_f1_std = cv_scores.get("cv_f1_std")
    evaluation.cv_recall_mean = cv_scores.get("cv_recall_mean")
    evaluation.cv_roc_auc_mean = cv_scores.get("cv_roc_auc_mean")

    if name in models_without_class_weighting():
        evaluation.notes.append(
            "Estimator does not support class weighting; trained on the natural class ratio."
        )

    logger.info(
        "[%s] f1=%.4f recall=%.4f roc_auc=%.4f accuracy=%.4f (train %.2fs)",
        name,
        evaluation.f1,
        evaluation.recall,
        evaluation.roc_auc,
        evaluation.accuracy,
        evaluation.train_time_seconds,
    )
    return pipeline, evaluation


def build_metadata(
    selection: ModelSelection,
    winning_evaluation: ModelEvaluation,
    feature_columns: list[str],
    numeric_features: list[str],
    categorical_features: list[str],
    transformed_feature_names: list[str],
    class_balance: dict[str, Any],
    dataset_path: Path,
    n_rows: int,
    cleaning_notes: list[str],
) -> dict[str, Any]:
    """Assemble ``model_metadata.json`` content."""
    return {
        "model_name": selection.model_name,
        "model_version": config.MODEL_VERSION,
        "target": config.TARGET_COLUMN,
        "features": feature_columns,
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "transformed_feature_count": len(transformed_feature_names),
        "transformed_feature_names": transformed_feature_names,
        "training_date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "random_state": config.RANDOM_STATE,
        "test_size": config.TEST_SIZE,
        "cv_folds": config.CV_FOLDS,
        "metrics": winning_evaluation.to_dict(),
        "selection_strategy": {
            "weights": config.SELECTION_WEIGHTS,
            "scored_on": selection.scored_on,
            "selection_score": selection.selection_score,
            "reason": selection.reason,
            "ranking": selection.ranking,
        },
        "class_balance": class_balance,
        "cleaning_notes": cleaning_notes,
        "risk_thresholds": {
            "medium": config.RISK_THRESHOLD_MEDIUM,
            "high": config.RISK_THRESHOLD_HIGH,
        },
        "dataset_name": config.DATASET_NAME,
        "dataset_source_url": config.DATASET_URL,
        "dataset_path": str(dataset_path),
        "dataset_rows_used": n_rows,
        "environment": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "pandas": pd.__version__,
            "xgboost_available": XGBOOST_AVAILABLE,
        },
    }


def run_training(
    dataset_path: Path | None = None,
    models_dir: Path | None = None,
    allow_download: bool = True,
    run_cv: bool = True,
) -> TrainingArtifacts:
    """Execute the full training pipeline and persist artifacts."""
    target_models_dir = Path(models_dir) if models_dir else config.MODELS_DIR
    target_models_dir.mkdir(parents=True, exist_ok=True)

    # 1. Acquire
    if dataset_path is not None:
        raw_path = Path(dataset_path)
    elif allow_download:
        raw_path = ensure_dataset()
    else:
        raw_path = config.RAW_DATASET_PATH

    # 2. Validate
    raw_frame = load_raw_dataset(raw_path)
    report = validate_dataset(raw_frame, path=raw_path)
    log_dataset_summary(report)

    # 3. Clean
    cleaned, cleaning_report = clean_dataset(raw_frame)

    # 4. Features / target
    features, target = split_features_target(cleaned)
    numeric_features, categorical_features = resolve_feature_types(features)
    class_balance = describe_class_balance(target)
    logger.info("Class balance: %s", class_balance)
    if class_balance["positive_rate"] < 0.4:
        logger.warning(
            "Target is imbalanced (%.2f%% churners). Using class weighting where supported.",
            100 * class_balance["positive_rate"],
        )

    # 5. Split — the test set is untouched until final evaluation.
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=config.TEST_SIZE,
        random_state=config.RANDOM_STATE,
        stratify=target,
    )
    logger.info("Train rows: %s | Test rows: %s", len(x_train), len(x_test))

    # 6. Train candidates
    scale_pos_weight = compute_scale_pos_weight(
        n_negative=int((y_train == 0).sum()), n_positive=int((y_train == 1).sum())
    )
    candidates = get_candidate_models(scale_pos_weight=scale_pos_weight)

    fitted_pipelines: dict[str, Pipeline] = {}
    results: list[ModelEvaluation] = []
    for name, estimator in candidates.items():
        pipeline, evaluation = train_single_model(
            name,
            estimator,
            numeric_features,
            categorical_features,
            x_train,
            y_train,
            x_test,
            y_test,
            run_cv=run_cv,
        )
        fitted_pipelines[name] = pipeline
        results.append(evaluation)

    if not results:
        raise MLPipelineError("No models were trained; cannot select a best model.")

    # 7. Select
    selection = select_best_model(results)
    log_comparison(results)
    logger.info("Selected model: %s", selection.model_name)
    logger.info("Selection reason: %s", selection.reason)

    # 8. Persist
    best_pipeline = fitted_pipelines[selection.model_name]
    fitted_preprocessor = best_pipeline.named_steps[PREPROCESSOR_STEP]
    fitted_estimator = best_pipeline.named_steps[MODEL_STEP]

    best_model_path = target_models_dir / config.BEST_MODEL_FILENAME
    preprocessor_path = target_models_dir / config.PREPROCESSOR_FILENAME
    joblib.dump(fitted_estimator, best_model_path)
    joblib.dump(fitted_preprocessor, preprocessor_path)

    winning_evaluation = next(item for item in results if item.model_name == selection.model_name)
    metadata = build_metadata(
        selection=selection,
        winning_evaluation=winning_evaluation,
        feature_columns=list(features.columns),
        numeric_features=numeric_features,
        categorical_features=categorical_features,
        transformed_feature_names=get_transformed_feature_names(fitted_preprocessor),
        class_balance=class_balance,
        dataset_path=raw_path,
        n_rows=len(cleaned),
        cleaning_notes=cleaning_report.notes,
    )
    metadata_path = target_models_dir / config.METADATA_FILENAME
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    csv_path, json_path = save_comparison_reports(
        results,
        models_dir=target_models_dir,
        extra={
            "selected_model": selection.model_name,
            "selection_reason": selection.reason,
            "class_balance": class_balance,
            "validation_warnings": report.warnings,
            "cleaning_notes": cleaning_report.notes,
        },
    )

    logger.info("Artifacts saved:")
    for path in (best_model_path, preprocessor_path, metadata_path, csv_path, json_path):
        logger.info("  %s", path)

    return TrainingArtifacts(
        best_model_path=best_model_path,
        preprocessor_path=preprocessor_path,
        metadata_path=metadata_path,
        comparison_csv_path=csv_path,
        comparison_json_path=json_path,
        selection=selection,
        results=results,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train the telecom churn models.")
    parser.add_argument("--dataset-path", default=None, help="Path to the raw CSV.")
    parser.add_argument("--models-dir", default=None, help="Directory for saved artifacts.")
    parser.add_argument(
        "--no-download", action="store_true", help="Fail instead of downloading a missing dataset."
    )
    parser.add_argument(
        "--no-cv", action="store_true", help="Skip cross-validation (faster, less reliable)."
    )
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = _parse_args()
    try:
        artifacts = run_training(
            dataset_path=Path(args.dataset_path) if args.dataset_path else None,
            models_dir=Path(args.models_dir) if args.models_dir else None,
            allow_download=not args.no_download,
            run_cv=not args.no_cv,
        )
    except (
        DatasetDownloadError,
        DatasetNotFoundError,
        DatasetValidationError,
        MLPipelineError,
    ) as exc:
        logger.error("Training failed: %s", exc)
        return 1

    frame = results_to_dataframe(artifacts.results)
    print("\nModel comparison\n" + frame.to_string(index=False))
    print(f"\nSelected model: {artifacts.selection.model_name}")
    print(f"Reason: {artifacts.selection.reason}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
