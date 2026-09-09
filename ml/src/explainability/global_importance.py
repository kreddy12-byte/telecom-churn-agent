"""Global feature importance: which factors drive churn across all customers.

Local vs global
---------------
``explainer.explain_customer`` answers "why is *this* customer at risk?".
This module answers "which features move the model the most *in general?*", by
averaging the magnitude of each feature's SHAP contribution across many
customers.

Data used
---------
The report is computed over the **training split**, reproduced with the same
``random_state=42`` stratified split as training. The test split is left out so
the report never becomes an indirect way of inspecting held-out data. Because
the explainer is linear, scoring all 5,634 training rows costs one matrix
multiplication, so no subsampling is needed by default; ``--sample-size`` takes
a deterministic sample when a cheaper run is wanted.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from ml.src import config
from ml.src.data.clean_dataset import clean_dataset
from ml.src.data.validate_dataset import load_raw_dataset
from ml.src.exceptions import DatasetNotFoundError, MLPipelineError
from ml.src.explainability.explainer import ChurnExplainer
from ml.src.logging_config import configure_logging, get_logger
from ml.src.preprocessing.pipeline import split_features_target

logger = get_logger(__name__)

GLOBAL_IMPORTANCE_FILENAME = "global_feature_importance.csv"


def load_training_features(
    sample_size: int | None = None, dataset_path: Path | None = None
) -> pd.DataFrame:
    """Return the cleaned training-split features used for the global report."""
    raw_frame = load_raw_dataset(dataset_path)
    cleaned, _ = clean_dataset(raw_frame)
    features, target = split_features_target(cleaned)

    x_train, _, _, _ = train_test_split(
        features,
        target,
        test_size=config.TEST_SIZE,
        random_state=config.RANDOM_STATE,
        stratify=target,
    )

    if sample_size is not None and sample_size < len(x_train):
        # Deterministic sample so the report is reproducible run to run.
        x_train = x_train.sample(n=sample_size, random_state=config.RANDOM_STATE)

    logger.info("Global importance will be computed over %s customers.", len(x_train))
    return x_train


def compute_global_importance(
    explainer: ChurnExplainer, features: pd.DataFrame
) -> pd.DataFrame:
    """Rank original features by mean absolute SHAP value.

    ``mean_absolute_shap`` measures *how much* a feature moves the prediction,
    regardless of direction — a feature that strongly pushes some customers
    toward churn and others away still matters a lot.

    ``mean_signed_shap`` keeps the direction, so a positive value means the
    feature pushes the average customer toward churn. Both are reported because
    either alone is misleading.
    """
    shap_by_feature = explainer.shap_by_feature(features)

    report = pd.DataFrame(
        {
            "feature": shap_by_feature.columns,
            "mean_absolute_shap": shap_by_feature.abs().mean(axis=0).to_numpy(),
            "mean_signed_shap": shap_by_feature.mean(axis=0).to_numpy(),
        }
    )
    report = report.sort_values("mean_absolute_shap", ascending=False).reset_index(drop=True)
    report["mean_absolute_shap"] = report["mean_absolute_shap"].round(6)
    report["mean_signed_shap"] = report["mean_signed_shap"].round(6)
    return report


def save_global_importance(report: pd.DataFrame, models_dir: Path | None = None) -> Path:
    """Write ``global_feature_importance.csv``."""
    target_dir = Path(models_dir) if models_dir else config.MODELS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)

    path = target_dir / GLOBAL_IMPORTANCE_FILENAME
    report.to_csv(path, index=False)
    logger.info("Global feature importance written to %s", path)
    return path


def generate_global_report(
    models_dir: Path | None = None,
    sample_size: int | None = None,
    dataset_path: Path | None = None,
    make_plots: bool = True,
) -> tuple[pd.DataFrame, Path]:
    """Compute, save, and optionally plot the global feature importance."""
    explainer = ChurnExplainer(models_dir=models_dir)
    features = load_training_features(sample_size=sample_size, dataset_path=dataset_path)

    report = compute_global_importance(explainer, features)
    csv_path = save_global_importance(report, models_dir=models_dir)

    if make_plots:
        from ml.src.explainability.plots import plot_global_importance

        plot_path = plot_global_importance(report, models_dir=models_dir)
        logger.info("Global importance plot saved to %s", plot_path)

    return report, csv_path


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Generate the global SHAP importance report.")
    parser.add_argument("--models-dir", default=None, help="Directory containing artifacts.")
    parser.add_argument("--dataset-path", default=None, help="Path to the raw CSV.")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=None,
        help="Use a deterministic sample of the training split instead of all rows.",
    )
    parser.add_argument("--no-plots", action="store_true", help="Skip plot generation.")
    args = parser.parse_args()

    try:
        report, csv_path = generate_global_report(
            models_dir=Path(args.models_dir) if args.models_dir else None,
            sample_size=args.sample_size,
            dataset_path=Path(args.dataset_path) if args.dataset_path else None,
            make_plots=not args.no_plots,
        )
    except (DatasetNotFoundError, MLPipelineError) as exc:
        logger.error("%s", exc)
        return 1

    print(f"\nGlobal feature importance ({csv_path})\n")
    print(report.to_string(index=False))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
