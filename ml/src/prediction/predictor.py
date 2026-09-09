"""Reusable prediction interface consumed by the FastAPI backend.

Usage from Python::

    from ml.src.prediction.predictor import predict_customer

    result = predict_customer({...customer fields...})
    # {"churn_probability": 0.87, "prediction": 1, "risk_level": "HIGH",
    #  "model_version": "1.0.0"}

Usage from the CLI (predicts a real row from the raw dataset)::

    python -m ml.src.prediction.predictor --row 0
    python -m ml.src.prediction.predictor --customer-id 7590-VHVEG
    python -m ml.src.prediction.predictor --json '{"tenure": 1, ...}'
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from ml.src import config
from ml.src.data.clean_dataset import prepare_feature_frame
from ml.src.exceptions import (
    InvalidPredictionInputError,
    MLPipelineError,
    ModelArtifactNotFoundError,
)
from ml.src.logging_config import configure_logging, get_logger

logger = get_logger(__name__)


class ChurnPredictor:
    """Loads trained artifacts once and serves churn predictions.

    Artifacts are loaded lazily so importing this module never requires a
    trained model to exist (useful for tests and for backend startup).
    """

    def __init__(self, models_dir: Path | str | None = None) -> None:
        self.models_dir = Path(models_dir) if models_dir else config.MODELS_DIR
        self._model: Any | None = None
        self._preprocessor: Any | None = None
        self._metadata: dict[str, Any] | None = None

    # ------------------------------------------------------------------ #
    # Artifact loading
    # ------------------------------------------------------------------ #

    def _artifact_path(self, filename: str) -> Path:
        path = self.models_dir / filename
        if not path.exists():
            raise ModelArtifactNotFoundError(
                f"Required artifact '{filename}' not found in {self.models_dir}. "
                "Train the model first: `python -m ml.src.training.train`."
            )
        return path

    def load(self) -> None:
        """Load model, preprocessor, and metadata from disk."""
        if self._model is not None and self._preprocessor is not None:
            return

        model_path = self._artifact_path(config.BEST_MODEL_FILENAME)
        preprocessor_path = self._artifact_path(config.PREPROCESSOR_FILENAME)
        metadata_path = self._artifact_path(config.METADATA_FILENAME)

        try:
            model = joblib.load(model_path)
            preprocessor = joblib.load(preprocessor_path)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise MLPipelineError(f"Failed to load model artifacts from {self.models_dir}: {exc}") from exc

        # Assign only after every artifact loaded, so a partial failure cannot
        # leave the predictor in a half-initialised state.
        self._model = model
        self._preprocessor = preprocessor
        self._metadata = metadata

        logger.info(
            "Loaded model '%s' version %s from %s",
            self.metadata.get("model_name", "unknown"),
            self.model_version,
            self.models_dir,
        )

    @property
    def metadata(self) -> dict[str, Any]:
        self.load()
        return self._metadata or {}

    @property
    def model_version(self) -> str:
        return str(self.metadata.get("model_version", config.MODEL_VERSION))

    @property
    def feature_columns(self) -> list[str]:
        features = self.metadata.get("features")
        if isinstance(features, list) and features:
            return [str(name) for name in features]
        return list(config.FEATURE_COLUMNS)

    @property
    def model(self) -> Any:
        """The fitted estimator (used by the explainability layer)."""
        self.load()
        return self._model

    @property
    def preprocessor(self) -> Any:
        """The fitted ColumnTransformer (used by the explainability layer)."""
        self.load()
        return self._preprocessor

    @property
    def numeric_features(self) -> list[str]:
        features = self.metadata.get("numeric_features")
        if isinstance(features, list) and features:
            return [str(name) for name in features]
        return list(config.NUMERIC_FEATURES)

    # ------------------------------------------------------------------ #
    # Input handling
    # ------------------------------------------------------------------ #

    def _to_frame(self, customer_data: Mapping[str, Any] | Sequence[Mapping[str, Any]]) -> pd.DataFrame:
        """Normalise supported input types into a DataFrame."""
        if isinstance(customer_data, Mapping):
            records = [dict(customer_data)]
        elif isinstance(customer_data, Sequence) and not isinstance(customer_data, (str, bytes)):
            records = []
            for index, item in enumerate(customer_data):
                if not isinstance(item, Mapping):
                    raise InvalidPredictionInputError(
                        f"Record at index {index} must be a mapping of feature name to value, "
                        f"got {type(item).__name__}."
                    )
                records.append(dict(item))
        else:
            raise InvalidPredictionInputError(
                "Prediction input must be a mapping (or a sequence of mappings), "
                f"got {type(customer_data).__name__}."
            )

        if not records:
            raise InvalidPredictionInputError("Prediction input contains no records.")
        if any(not record for record in records):
            raise InvalidPredictionInputError("Prediction input contains an empty record.")

        return pd.DataFrame.from_records(records)

    def validate_input(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Validate and align raw input to the trained feature schema.

        Raises:
            InvalidPredictionInputError: On missing features, null-only required
                fields, or numeric fields that cannot be parsed.
        """
        expected = self.feature_columns

        missing = [column for column in expected if column not in frame.columns]
        if missing:
            raise InvalidPredictionInputError(
                f"Missing required feature(s): {missing}. Expected features: {expected}."
            )

        extra = [column for column in frame.columns if column not in expected]
        if extra:
            logger.debug("Ignoring non-feature columns in prediction input: %s", extra)

        aligned = frame[expected].copy()
        prepared = prepare_feature_frame(aligned)

        for column in self.numeric_features:
            if column not in prepared.columns:
                continue
            provided = aligned[column].notna()
            unparseable = provided & prepared[column].isna()
            if unparseable.any():
                bad_rows = prepared.index[unparseable].tolist()
                raise InvalidPredictionInputError(
                    f"Feature '{column}' must be numeric; unparseable value(s) at row(s) {bad_rows}."
                )

        fully_missing = [column for column in expected if prepared[column].isna().all()]
        if len(fully_missing) == len(expected):
            raise InvalidPredictionInputError("All feature values are missing; cannot predict.")

        return prepared

    # ------------------------------------------------------------------ #
    # Prediction
    # ------------------------------------------------------------------ #

    def _probabilities(self, transformed: np.ndarray) -> np.ndarray:
        model = self._model
        if hasattr(model, "predict_proba"):
            return np.asarray(model.predict_proba(transformed))[:, 1]
        if hasattr(model, "decision_function"):
            scores = np.asarray(model.decision_function(transformed))
            return 1.0 / (1.0 + np.exp(-scores))
        raise MLPipelineError(
            f"Loaded model {type(model).__name__} cannot produce probabilities."
        )

    def transform_customers(
        self, customers: Sequence[Mapping[str, Any]] | Mapping[str, Any]
    ) -> tuple[pd.DataFrame, np.ndarray]:
        """Validate, clean, and transform customer records.

        Returns both the cleaned raw-space frame (human-readable feature values)
        and the transformed matrix the model consumes. The explainability layer
        reuses this so input handling is never duplicated.
        """
        self.load()
        frame = self._to_frame(customers)
        prepared = self.validate_input(frame)
        transformed = np.asarray(self._preprocessor.transform(prepared))
        return prepared, transformed

    def predict_batch(
        self, customers: Sequence[Mapping[str, Any]] | Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        """Predict churn for one or more customers."""
        _, transformed = self.transform_customers(customers)
        probabilities = self._probabilities(transformed)

        results: list[dict[str, Any]] = []
        for probability in probabilities:
            value = float(probability)
            results.append(
                {
                    "churn_probability": round(value, 4),
                    "prediction": int(value >= 0.5),
                    "risk_level": config.risk_level_for(value),
                    "model_version": self.model_version,
                }
            )
        return results

    def predict(self, customer_data: Mapping[str, Any]) -> dict[str, Any]:
        """Predict churn for a single customer."""
        if not isinstance(customer_data, Mapping):
            raise InvalidPredictionInputError(
                f"Expected a mapping of feature name to value, got {type(customer_data).__name__}."
            )
        return self.predict_batch([customer_data])[0]


@lru_cache(maxsize=4)
def get_predictor(models_dir: str | None = None) -> ChurnPredictor:
    """Return a cached predictor so artifacts load once per process."""
    return ChurnPredictor(models_dir=models_dir)


def predict_customer(
    customer_data: Mapping[str, Any], models_dir: Path | str | None = None
) -> dict[str, Any]:
    """Predict churn for a single customer record.

    Returns:
        ``{"churn_probability": float, "prediction": int, "risk_level": str,
        "model_version": str}``
    """
    predictor = get_predictor(str(models_dir) if models_dir else None)
    return predictor.predict(customer_data)


def predict_customers(
    customers: Sequence[Mapping[str, Any]], models_dir: Path | str | None = None
) -> list[dict[str, Any]]:
    """Predict churn for a batch of customer records."""
    predictor = get_predictor(str(models_dir) if models_dir else None)
    return predictor.predict_batch(customers)


# ---------------------------------------------------------------------- #
# CLI
# ---------------------------------------------------------------------- #


def load_customer_from_dataset(row: int | None, customer_id: str | None) -> dict[str, Any]:
    """Read one real record from the raw dataset for a smoke prediction."""
    from ml.src.data.validate_dataset import load_raw_dataset

    frame = load_raw_dataset()
    if customer_id:
        matches = frame[frame[config.ID_COLUMN].astype(str).str.strip() == customer_id]
        if matches.empty:
            raise InvalidPredictionInputError(
                f"No customer with {config.ID_COLUMN}='{customer_id}' in the raw dataset."
            )
        record = matches.iloc[0]
    else:
        index = row or 0
        if index < 0 or index >= len(frame):
            raise InvalidPredictionInputError(
                f"Row {index} is out of range for a dataset with {len(frame)} rows."
            )
        record = frame.iloc[index]

    return {key: value for key, value in record.to_dict().items() if key != config.TARGET_COLUMN}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predict churn for a customer record.")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--json", dest="payload", default=None, help="Customer record as JSON.")
    source.add_argument("--file", default=None, help="Path to a JSON file with a customer record.")
    source.add_argument("--row", type=int, default=None, help="Row index from the raw dataset.")
    source.add_argument("--customer-id", default=None, help="customerID from the raw dataset.")
    parser.add_argument("--models-dir", default=None, help="Directory containing artifacts.")
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = _parse_args()

    try:
        if args.payload:
            customer = json.loads(args.payload)
        elif args.file:
            customer = json.loads(Path(args.file).read_text(encoding="utf-8"))
        else:
            customer = load_customer_from_dataset(args.row, args.customer_id)

        result = predict_customer(customer, models_dir=args.models_dir)
    except json.JSONDecodeError as exc:
        logger.error("Input is not valid JSON: %s", exc)
        return 1
    except (InvalidPredictionInputError, ModelArtifactNotFoundError, MLPipelineError) as exc:
        logger.error("%s", exc)
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
