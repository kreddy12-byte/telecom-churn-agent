"""SHAP explanations for individual churn predictions.

What this module answers
------------------------
"The model says this customer is likely to churn — *why*?"

Scope of the SHAP values produced here
--------------------------------------
The selected model is a Logistic Regression, so ``shap.LinearExplainer`` is used:
it is exact for linear models and costs a single matrix multiplication, unlike
the sampling-based generic explainers.

**SHAP values are computed on the model's log-odds output** (scikit-learn's
``decision_function``), not on the probability. That is the scale on which a
logistic regression is additive, which is what makes the SHAP decomposition
exact::

    log_odds(customer) = base_value + sum(all SHAP values)

Probabilities are *not* additive (they are squashed through a sigmoid), so
reporting SHAP values as "probability points" would be mathematically wrong. The
churn probability is still reported alongside, produced by the existing
prediction interface.

Sign convention
---------------
* SHAP value > 0 → pushes the log-odds up → **increases** churn risk.
* SHAP value < 0 → pushes the log-odds down → **decreases** churn risk.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import shap

from ml.src import config
from ml.src.exceptions import InvalidPredictionInputError, MLPipelineError, ModelArtifactNotFoundError
from ml.src.explainability.background import load_or_build_background
from ml.src.explainability.feature_mapping import (
    aggregate_shap_by_feature,
    aggregate_shap_matrix,
    build_feature_map,
    group_indices_by_feature,
)
from ml.src.logging_config import configure_logging, get_logger
from ml.src.prediction.predictor import ChurnPredictor

logger = get_logger(__name__)

DEFAULT_TOP_K = 5

DIRECTION_INCREASES = "increases_risk"
DIRECTION_DECREASES = "decreases_risk"

# The scale the SHAP values live on; surfaced in the output so no consumer can
# mistake them for probability points.
EXPLAINED_OUTPUT = "log_odds"


class ChurnExplainer:
    """Produces SHAP explanations for the trained churn model.

    The explainer reuses :class:`~ml.src.prediction.predictor.ChurnPredictor` for
    artifact loading, input validation, and preprocessing, so explanation and
    prediction can never drift apart.
    """

    def __init__(
        self,
        models_dir: Path | str | None = None,
        background: np.ndarray | None = None,
    ) -> None:
        self.models_dir = Path(models_dir) if models_dir else config.MODELS_DIR
        self.predictor = ChurnPredictor(models_dir=self.models_dir)

        self._background = background
        self._explainer: shap.LinearExplainer | None = None
        self._feature_map: list | None = None
        self._groups: dict[str, list[int]] | None = None

    # =========================================================
    # 1. LOAD MODEL AND PREPROCESSOR
    # =========================================================

    def load(self) -> None:
        """Load artifacts and build the SHAP explainer (idempotent)."""
        if self._explainer is not None:
            return

        # Raises ModelArtifactNotFoundError with actionable guidance if the model
        # has not been trained yet.
        self.predictor.load()

        model = self.predictor.model
        preprocessor = self.predictor.preprocessor

        if not hasattr(model, "coef_"):
            raise MLPipelineError(
                f"The saved model is a {type(model).__name__}, which is not linear. "
                "shap.LinearExplainer only supports linear models; retrain or extend "
                "this module with a model-appropriate explainer before explaining."
            )

        # Feature bookkeeping: which transformed column belongs to which feature.
        self._feature_map = build_feature_map(preprocessor)
        self._groups = group_indices_by_feature(self._feature_map)

        if self._background is None:
            self._background = load_or_build_background(preprocessor, self.models_dir)

        background = np.asarray(self._background)
        if background.shape[1] != len(self._feature_map):
            raise MLPipelineError(
                f"Background data has {background.shape[1]} columns but the preprocessor "
                f"produces {len(self._feature_map)}. The background is stale — delete "
                "shap_background.joblib and let it rebuild."
            )

        # max_samples is set explicitly to the full background size; otherwise SHAP
        # silently subsamples to 100 rows and warns.
        masker = shap.maskers.Independent(background, max_samples=background.shape[0])
        self._explainer = shap.LinearExplainer(model, masker)

        logger.info(
            "SHAP LinearExplainer ready: %s transformed columns, %s background rows, "
            "base value (log-odds) %.4f",
            len(self._feature_map),
            background.shape[0],
            float(self.base_value),
        )

    @property
    def base_value(self) -> float:
        """Average model log-odds over the background distribution."""
        self.load()
        return float(np.asarray(self._explainer.expected_value).ravel()[0])

    @property
    def background(self) -> np.ndarray:
        """The reference distribution SHAP compares each customer against."""
        self.load()
        return np.asarray(self._background)

    @property
    def feature_map(self) -> list:
        self.load()
        return self._feature_map or []

    @property
    def transformed_feature_count(self) -> int:
        return len(self.feature_map)

    # =========================================================
    # 2. PREPARE CUSTOMER INPUT
    # =========================================================

    def _prepare_customer(
        self, customer_data: Mapping[str, Any]
    ) -> tuple[pd.DataFrame, np.ndarray]:
        """Validate and transform one customer record.

        Delegates to the predictor so validation rules and cleaning are shared.
        """
        if not isinstance(customer_data, Mapping):
            raise InvalidPredictionInputError(
                "Expected a mapping of feature name to value, got "
                f"{type(customer_data).__name__}."
            )
        return self.predictor.transform_customers([customer_data])

    # =========================================================
    # 3. GENERATE SHAP EXPLANATION
    # =========================================================

    def _compute_shap_values(self, transformed: np.ndarray) -> np.ndarray:
        """Return SHAP values in the transformed space, shape (n_rows, n_columns)."""
        self.load()
        values = np.asarray(self._explainer.shap_values(transformed))
        return np.atleast_2d(values)

    def verify_additivity(self, transformed: np.ndarray, tolerance: float = 1e-6) -> None:
        """Assert that base value + SHAP values reproduce the model's log-odds.

        This is the strongest available evidence that the explanation comes from
        the real model rather than from an approximation or a stub.
        """
        shap_values = self._compute_shap_values(transformed)
        reconstructed = shap_values.sum(axis=1) + self.base_value
        actual = np.asarray(self.predictor.model.decision_function(transformed)).ravel()

        largest_error = float(np.abs(reconstructed - actual).max())
        if largest_error > tolerance:
            raise MLPipelineError(
                "SHAP values do not reconstruct the model output "
                f"(largest error {largest_error:.3e} > tolerance {tolerance:.1e}); "
                "the explanation cannot be trusted."
            )

    # =========================================================
    # 4. IDENTIFY TOP FEATURES
    # =========================================================

    def _rank_drivers(
        self,
        aggregated_shap: dict[str, float],
        customer_row: pd.Series,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Sort features by absolute contribution and format the top ``top_k``.

        ``impact`` is the feature's share of the customer's total absolute
        contribution, so it always falls in [0, 1] and the drivers are directly
        comparable. The raw signed log-odds contribution is reported alongside as
        ``shap_value`` for callers that need the underlying number.
        """
        total_absolute_contribution = sum(abs(value) for value in aggregated_shap.values())

        ranked_features = sorted(
            aggregated_shap.items(), key=lambda item: abs(item[1]), reverse=True
        )

        drivers: list[dict[str, Any]] = []
        for feature_name, shap_value in ranked_features[:top_k]:
            relative_impact = (
                abs(shap_value) / total_absolute_contribution
                if total_absolute_contribution > 0
                else 0.0
            )
            drivers.append(
                {
                    "feature": feature_name,
                    "value": _to_python_scalar(customer_row.get(feature_name)),
                    "impact": round(relative_impact, 4),
                    "direction": (
                        DIRECTION_INCREASES if shap_value > 0 else DIRECTION_DECREASES
                    ),
                    "shap_value": round(float(shap_value), 4),
                }
            )
        return drivers

    # =========================================================
    # 5. FORMAT EXPLANATION
    # =========================================================

    def explain(
        self, customer_data: Mapping[str, Any], top_k: int = DEFAULT_TOP_K
    ) -> dict[str, Any]:
        """Explain the churn prediction for a single customer.

        Args:
            customer_data: Raw customer record (the same shape accepted by
                ``predict_customer``). Extra keys such as ``customerID`` are
                allowed and ignored by the model.
            top_k: How many drivers to return, ranked by absolute contribution.

        Returns:
            ``{"customer_id", "churn_probability", "prediction", "risk_level",
            "model_version", "explained_output", "base_value", "top_drivers"}``
        """
        if top_k < 1:
            raise InvalidPredictionInputError(f"top_k must be at least 1, got {top_k}.")

        prepared_frame, transformed = self._prepare_customer(customer_data)

        shap_values = self._compute_shap_values(transformed)[0]
        aggregated_shap = aggregate_shap_by_feature(shap_values, self._groups or {})

        # Reuse the prediction interface so probability and risk band cannot
        # disagree with what the API would return for the same customer.
        prediction = self.predictor.predict(customer_data)

        return {
            "customer_id": _extract_customer_id(customer_data),
            "churn_probability": prediction["churn_probability"],
            "prediction": prediction["prediction"],
            "risk_level": prediction["risk_level"],
            "model_version": prediction["model_version"],
            "explained_output": EXPLAINED_OUTPUT,
            "base_value": round(self.base_value, 4),
            "top_drivers": self._rank_drivers(
                aggregated_shap, prepared_frame.iloc[0], top_k
            ),
        }

    # ------------------------------------------------------------------ #
    # Batch / frame helpers (used by the global importance report)
    # ------------------------------------------------------------------ #

    def explain_many(
        self, customers: Sequence[Mapping[str, Any]], top_k: int = DEFAULT_TOP_K
    ) -> list[dict[str, Any]]:
        """Explain several customers."""
        return [self.explain(customer, top_k=top_k) for customer in customers]

    def shap_by_feature(self, features: pd.DataFrame) -> pd.DataFrame:
        """Aggregated per-original-feature SHAP values for a frame of customers.

        Args:
            features: Raw-space feature rows (validated like prediction input).

        Returns:
            DataFrame of shape ``(n_customers, n_original_features)``.
        """
        self.load()
        prepared = self.predictor.validate_input(features)
        transformed = np.asarray(self.predictor.preprocessor.transform(prepared))
        shap_matrix = self._compute_shap_values(transformed)

        aggregated = aggregate_shap_matrix(shap_matrix, self._groups or {})
        return pd.DataFrame(aggregated, index=features.index)


# --------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------- #


def _to_python_scalar(value: Any) -> Any:
    """Convert numpy/pandas scalars to JSON-serialisable Python values."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    if pd.isna(value):
        return None
    return value


def _extract_customer_id(customer_data: Mapping[str, Any]) -> str | None:
    """Read the identifier from the record when the caller supplied one."""
    raw_value = customer_data.get(config.ID_COLUMN)
    return str(raw_value) if raw_value is not None else None


@lru_cache(maxsize=4)
def get_explainer(models_dir: str | None = None) -> ChurnExplainer:
    """Return a cached explainer so artifacts and SHAP setup load once."""
    return ChurnExplainer(models_dir=models_dir)


def explain_customer(
    customer_data: Mapping[str, Any],
    top_k: int = DEFAULT_TOP_K,
    models_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Explain one customer's churn prediction. Main entrypoint for the backend."""
    explainer = get_explainer(str(models_dir) if models_dir else None)
    return explainer.explain(customer_data, top_k=top_k)


# --------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------- #


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Explain a churn prediction with SHAP."
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--json", dest="payload", default=None, help="Customer record as JSON.")
    source.add_argument("--file", default=None, help="Path to a JSON customer record.")
    source.add_argument("--row", type=int, default=None, help="Row index from the raw dataset.")
    source.add_argument("--customer-id", default=None, help="customerID from the raw dataset.")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K, help="Number of drivers.")
    parser.add_argument("--models-dir", default=None, help="Directory containing artifacts.")
    parser.add_argument("--plot", action="store_true", help="Also save an explanation plot.")
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = _parse_args()

    # Imported lazily so the CLI's dataset helpers stay optional for library use.
    from ml.src.prediction.predictor import load_customer_from_dataset

    try:
        if args.payload:
            customer = json.loads(args.payload)
        elif args.file:
            customer = json.loads(Path(args.file).read_text(encoding="utf-8"))
        else:
            customer = load_customer_from_dataset(args.row, args.customer_id)

        explainer = ChurnExplainer(models_dir=args.models_dir)
        explanation = explainer.explain(customer, top_k=args.top_k)

        if args.plot:
            from ml.src.explainability.plots import plot_customer_explanation

            plot_path = plot_customer_explanation(explanation)
            logger.info("Explanation plot saved to %s", plot_path)

    except json.JSONDecodeError as exc:
        logger.error("Input is not valid JSON: %s", exc)
        return 1
    except (InvalidPredictionInputError, ModelArtifactNotFoundError, MLPipelineError) as exc:
        logger.error("%s", exc)
        return 1

    print(json.dumps(explanation, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
