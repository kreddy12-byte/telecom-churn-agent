"""Shared fixtures for the ML test suite.

Tests never download the real dataset; they use a small synthetic frame that
matches the IBM Telco schema, including its known quirks (blank TotalCharges
for zero-tenure customers).
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from ml.src import config
from ml.src.data.clean_dataset import clean_dataset
from ml.src.explainability.background import save_background
from ml.src.preprocessing.pipeline import (
    build_preprocessor,
    resolve_feature_types,
    split_features_target,
)

N_SYNTHETIC_ROWS = 200


def make_synthetic_raw_frame(n_rows: int = N_SYNTHETIC_ROWS, seed: int = 42) -> pd.DataFrame:
    """Build a synthetic dataset with the same schema as the raw Telco CSV."""
    rng = np.random.default_rng(seed)

    contracts = rng.choice(["Month-to-month", "One year", "Two year"], size=n_rows, p=[0.6, 0.2, 0.2])
    tenure = rng.integers(0, 72, size=n_rows)
    monthly_charges = np.round(rng.uniform(18.0, 120.0, size=n_rows), 2)

    # Churn is driven by contract type and tenure so models can learn a signal.
    churn_score = (
        0.55 * (contracts == "Month-to-month")
        + 0.35 * (tenure < 12)
        + 0.20 * (monthly_charges > 80)
        + rng.normal(0, 0.2, size=n_rows)
    )
    churn = np.where(churn_score > 0.6, "Yes", "No")

    frame = pd.DataFrame(
        {
            "customerID": [f"C{index:05d}" for index in range(n_rows)],
            "gender": rng.choice(["Male", "Female"], size=n_rows),
            "SeniorCitizen": rng.integers(0, 2, size=n_rows),
            "Partner": rng.choice(["Yes", "No"], size=n_rows),
            "Dependents": rng.choice(["Yes", "No"], size=n_rows),
            "tenure": tenure,
            "PhoneService": rng.choice(["Yes", "No"], size=n_rows),
            "MultipleLines": rng.choice(["Yes", "No", "No phone service"], size=n_rows),
            "InternetService": rng.choice(["DSL", "Fiber optic", "No"], size=n_rows),
            "OnlineSecurity": rng.choice(["Yes", "No", "No internet service"], size=n_rows),
            "OnlineBackup": rng.choice(["Yes", "No", "No internet service"], size=n_rows),
            "DeviceProtection": rng.choice(["Yes", "No", "No internet service"], size=n_rows),
            "TechSupport": rng.choice(["Yes", "No", "No internet service"], size=n_rows),
            "StreamingTV": rng.choice(["Yes", "No", "No internet service"], size=n_rows),
            "StreamingMovies": rng.choice(["Yes", "No", "No internet service"], size=n_rows),
            "Contract": contracts,
            "PaperlessBilling": rng.choice(["Yes", "No"], size=n_rows),
            "PaymentMethod": rng.choice(
                ["Electronic check", "Mailed check", "Bank transfer (automatic)", "Credit card (automatic)"],
                size=n_rows,
            ),
            "MonthlyCharges": monthly_charges,
            "TotalCharges": np.round(monthly_charges * np.maximum(tenure, 1), 2).astype(str),
            "Churn": churn,
        }
    )

    # Reproduce the real dataset quirk: blank TotalCharges for zero-tenure rows.
    zero_tenure_index = frame.index[frame["tenure"] == 0]
    frame.loc[zero_tenure_index, "TotalCharges"] = " "
    if len(zero_tenure_index) == 0:
        frame.loc[0, "tenure"] = 0
        frame.loc[0, "TotalCharges"] = " "

    return frame


@pytest.fixture
def raw_frame() -> pd.DataFrame:
    """Synthetic raw dataset (uncleaned)."""
    return make_synthetic_raw_frame()


@pytest.fixture
def cleaned_frame(raw_frame: pd.DataFrame) -> pd.DataFrame:
    """Synthetic dataset after deterministic cleaning."""
    cleaned, _ = clean_dataset(raw_frame)
    return cleaned


@pytest.fixture
def sample_customer(raw_frame: pd.DataFrame) -> dict:
    """A single raw customer record without the target column."""
    record = raw_frame.iloc[0].to_dict()
    record.pop(config.TARGET_COLUMN, None)
    return record


@pytest.fixture
def trained_models_dir(tmp_path: Path, cleaned_frame: pd.DataFrame) -> Path:
    """Train a small real model on synthetic data and persist the artifacts.

    This mirrors what ``ml.src.training.train`` saves, so prediction tests
    exercise the real load/transform/predict path without a full training run.
    """
    features, target = split_features_target(cleaned_frame)
    numeric_features, categorical_features = resolve_feature_types(features)

    preprocessor = build_preprocessor(numeric_features, categorical_features)
    transformed = preprocessor.fit_transform(features)

    model = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=config.RANDOM_STATE)
    model.fit(transformed, target)

    models_dir = tmp_path / "models"
    models_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, models_dir / config.BEST_MODEL_FILENAME)
    joblib.dump(preprocessor, models_dir / config.PREPROCESSOR_FILENAME)

    metadata = {
        "model_name": "LogisticRegression",
        "model_version": config.MODEL_VERSION,
        "target": config.TARGET_COLUMN,
        "features": list(features.columns),
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "dataset_name": "synthetic-test-fixture",
        "random_state": config.RANDOM_STATE,
        "metrics": {},
    }
    (models_dir / config.METADATA_FILENAME).write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    # SHAP reference distribution, mirroring what a real deployment ships.
    save_background(transformed, models_dir)

    return models_dir


@pytest.fixture
def explainer(trained_models_dir: Path):
    """A ChurnExplainer backed by the real (small) model trained above."""
    from ml.src.explainability.explainer import ChurnExplainer

    return ChurnExplainer(models_dir=trained_models_dir)


@pytest.fixture
def feature_frame(cleaned_frame: pd.DataFrame) -> pd.DataFrame:
    """Raw-space feature rows without the target column."""
    features, _ = split_features_target(cleaned_frame)
    return features
