"""Feature/target separation and the fitted preprocessing pipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.src import config
from ml.src.exceptions import DatasetValidationError
from ml.src.logging_config import get_logger

logger = get_logger(__name__)

NUMERIC_STEP = "numeric"
CATEGORICAL_STEP = "categorical"


def split_features_target(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Split a cleaned dataset into the feature matrix and binary target.

    The identifier column is intentionally excluded from the features.
    """
    if config.TARGET_COLUMN not in frame.columns:
        raise DatasetValidationError(
            f"Cannot split features: target column '{config.TARGET_COLUMN}' is missing."
        )

    available = [column for column in config.FEATURE_COLUMNS if column in frame.columns]
    missing = [column for column in config.FEATURE_COLUMNS if column not in frame.columns]
    if missing:
        raise DatasetValidationError(f"Cannot split features: missing columns {missing}.")

    features = frame[available].copy()
    target = frame[config.TARGET_COLUMN].copy()
    return features, target


def resolve_feature_types(features: pd.DataFrame) -> tuple[list[str], list[str]]:
    """Return the numeric and categorical feature names present in ``features``."""
    numeric = [column for column in config.NUMERIC_FEATURES if column in features.columns]
    categorical = [column for column in config.CATEGORICAL_FEATURES if column in features.columns]

    unclassified = set(features.columns) - set(numeric) - set(categorical)
    if unclassified:
        logger.warning("Columns not covered by the preprocessor will be dropped: %s", sorted(unclassified))

    return numeric, categorical


def _build_one_hot_encoder() -> OneHotEncoder:
    """Create a dense OneHotEncoder across scikit-learn versions."""
    try:
        return OneHotEncoder(handle_unknown="ignore", sparse_output=False)
    except TypeError:  # scikit-learn < 1.2
        return OneHotEncoder(handle_unknown="ignore", sparse=False)


def build_preprocessor(
    numeric_features: list[str], categorical_features: list[str]
) -> ColumnTransformer:
    """Build the unfitted preprocessing ColumnTransformer.

    Numeric: median imputation + standard scaling.
    Categorical: most-frequent imputation + one-hot encoding with
    ``handle_unknown="ignore"`` so unseen categories at inference do not fail.
    """
    numeric_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("encoder", _build_one_hot_encoder()),
        ]
    )

    return ColumnTransformer(
        transformers=[
            (NUMERIC_STEP, numeric_pipeline, numeric_features),
            (CATEGORICAL_STEP, categorical_pipeline, categorical_features),
        ],
        remainder="drop",
        verbose_feature_names_out=False,
    )


def build_preprocessor_for(features: pd.DataFrame) -> ColumnTransformer:
    """Convenience wrapper that infers feature types from a DataFrame."""
    numeric, categorical = resolve_feature_types(features)
    return build_preprocessor(numeric, categorical)


def get_transformed_feature_names(preprocessor: ColumnTransformer) -> list[str]:
    """Return output feature names of a fitted preprocessor.

    Used later by the SHAP explainability layer, so it lives with the pipeline.
    """
    try:
        return [str(name) for name in preprocessor.get_feature_names_out()]
    except (AttributeError, ValueError) as exc:  # pragma: no cover - version guard
        logger.warning("Could not resolve transformed feature names: %s", exc)
        return []


def transform_features(preprocessor: ColumnTransformer, features: pd.DataFrame) -> np.ndarray:
    """Transform a feature frame with a fitted preprocessor."""
    transformed = preprocessor.transform(features)
    return np.asarray(transformed)
