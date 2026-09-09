"""Central configuration for the churn ML pipeline.

All paths are resolved relative to this file so the pipeline works regardless of
the current working directory. Directory locations can be overridden with
environment variables to support containerized deployments.
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Paths
# --------------------------------------------------------------------------- #

ML_DIR: Path = Path(__file__).resolve().parents[1]
PROJECT_ROOT: Path = ML_DIR.parent


def _dir_from_env(env_var: str, default: Path) -> Path:
    """Return a directory path, overridable through an environment variable."""
    raw_value = os.getenv(env_var)
    return Path(raw_value).expanduser().resolve() if raw_value else default


DATA_DIR: Path = _dir_from_env("ML_DATA_DIR", ML_DIR / "data")
RAW_DATA_DIR: Path = DATA_DIR / "raw"
MODELS_DIR: Path = _dir_from_env("ML_MODELS_DIR", ML_DIR / "models")

RAW_DATASET_FILENAME: str = "telco_customer_churn.csv"
RAW_DATASET_PATH: Path = RAW_DATA_DIR / RAW_DATASET_FILENAME

BEST_MODEL_FILENAME: str = "best_model.joblib"
PREPROCESSOR_FILENAME: str = "preprocessor.joblib"
METADATA_FILENAME: str = "model_metadata.json"
COMPARISON_CSV_FILENAME: str = "model_comparison.csv"
COMPARISON_JSON_FILENAME: str = "model_comparison.json"

# --------------------------------------------------------------------------- #
# Dataset
# --------------------------------------------------------------------------- #

DATASET_NAME: str = "IBM Telco Customer Churn"

# Primary source is IBM's own public repository for this dataset.
DATASET_URL: str = (
    "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/"
    "master/data/Telco-Customer-Churn.csv"
)

# Fallbacks are only used when the primary source is unreachable. Each must be a
# raw CSV of the *same* IBM Telco dataset; the download step validates schema
# after fetching so a mismatched file is rejected instead of silently accepted.
DATASET_FALLBACK_URLS: tuple[str, ...] = (
    "https://raw.githubusercontent.com/IBM/telco-customer-churn-on-icp4d/"
    "master/data/Telco-Customer-Churn.csv",
)

TARGET_COLUMN: str = "Churn"
ID_COLUMN: str = "customerID"

TARGET_POSITIVE_LABEL: str = "Yes"
TARGET_NEGATIVE_LABEL: str = "No"
TARGET_MAPPING: dict[str, int] = {TARGET_NEGATIVE_LABEL: 0, TARGET_POSITIVE_LABEL: 1}

NUMERIC_FEATURES: tuple[str, ...] = (
    "SeniorCitizen",
    "tenure",
    "MonthlyCharges",
    "TotalCharges",
)

CATEGORICAL_FEATURES: tuple[str, ...] = (
    "gender",
    "Partner",
    "Dependents",
    "PhoneService",
    "MultipleLines",
    "InternetService",
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
    "Contract",
    "PaperlessBilling",
    "PaymentMethod",
)

FEATURE_COLUMNS: tuple[str, ...] = NUMERIC_FEATURES + CATEGORICAL_FEATURES

REQUIRED_COLUMNS: tuple[str, ...] = (ID_COLUMN,) + FEATURE_COLUMNS + (TARGET_COLUMN,)

# Columns stored as text in the raw CSV that must be numeric for modelling.
NUMERIC_COERCION_COLUMNS: tuple[str, ...] = ("TotalCharges", "MonthlyCharges", "tenure")

# Columns that must never contain negative values.
NON_NEGATIVE_COLUMNS: tuple[str, ...] = (
    "tenure",
    "MonthlyCharges",
    "TotalCharges",
)

# --------------------------------------------------------------------------- #
# Training
# --------------------------------------------------------------------------- #

RANDOM_STATE: int = 42
TEST_SIZE: float = 0.2
CV_FOLDS: int = 5

MODEL_VERSION: str = "1.0.0"

# Weighted score used for best-model selection. Recall and F1 dominate because a
# missed churner costs more than a wasted retention offer.
SELECTION_WEIGHTS: dict[str, float] = {
    "f1": 0.45,
    "recall": 0.35,
    "roc_auc": 0.20,
}

# --------------------------------------------------------------------------- #
# Risk banding
# --------------------------------------------------------------------------- #

RISK_THRESHOLD_MEDIUM: float = 0.30
RISK_THRESHOLD_HIGH: float = 0.60

RISK_LEVEL_LOW: str = "LOW"
RISK_LEVEL_MEDIUM: str = "MEDIUM"
RISK_LEVEL_HIGH: str = "HIGH"


def risk_level_for(probability: float) -> str:
    """Map a churn probability to the shared LOW/MEDIUM/HIGH risk contract."""
    if probability < RISK_THRESHOLD_MEDIUM:
        return RISK_LEVEL_LOW
    if probability < RISK_THRESHOLD_HIGH:
        return RISK_LEVEL_MEDIUM
    return RISK_LEVEL_HIGH


def ensure_directories() -> None:
    """Create the data and model directories if they do not exist yet."""
    RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
