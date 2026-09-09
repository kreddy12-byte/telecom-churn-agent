"""End-to-end integration test using the real trained model and SHAP explainer.

Skipped automatically when the model artifacts or the raw dataset are absent, so
a fresh clone can still run the rest of the agent suite. Everything else in
``agent/tests`` uses synthetic evidence and never touches the ML stack.
"""

from __future__ import annotations

import pytest

from ml.src import config

VERIFICATION_CUSTOMER_ID = "7590-VHVEG"

REQUIRED_ARTIFACTS = [
    config.MODELS_DIR / config.BEST_MODEL_FILENAME,
    config.MODELS_DIR / config.PREPROCESSOR_FILENAME,
    config.MODELS_DIR / config.METADATA_FILENAME,
    config.RAW_DATA_DIR / config.RAW_DATASET_FILENAME,
]

pytestmark = pytest.mark.skipif(
    not all(path.exists() for path in REQUIRED_ARTIFACTS),
    reason="Trained model artifacts or raw dataset not available; run the ML pipeline first.",
)


@pytest.fixture(scope="module")
def real_evidence():
    from agent.services.evidence_builder import build_evidence_for_dataset_customer

    return build_evidence_for_dataset_customer(VERIFICATION_CUSTOMER_ID)


# =========================================================
# 1. EVIDENCE MATCHES THE EXISTING ML CONTRACTS
# =========================================================


def test_evidence_matches_the_prediction_contract(real_evidence) -> None:
    from ml.src.prediction.predictor import load_customer_from_dataset, predict_customer

    customer = load_customer_from_dataset(row=None, customer_id=VERIFICATION_CUSTOMER_ID)
    prediction = predict_customer(customer)

    assert real_evidence.customer_id == VERIFICATION_CUSTOMER_ID
    assert real_evidence.churn_probability == prediction["churn_probability"]
    assert real_evidence.risk_level == prediction["risk_level"]
    assert real_evidence.prediction == prediction["prediction"]
    assert real_evidence.model_version == prediction["model_version"]


def test_evidence_carries_real_shap_drivers(real_evidence) -> None:
    assert real_evidence.top_drivers
    assert real_evidence.explained_output == "log_odds"
    # Drivers arrive ranked by absolute contribution.
    impacts = [driver.impact for driver in real_evidence.top_drivers]
    assert impacts == sorted(impacts, reverse=True)


# =========================================================
# 2. FULL PIPELINE
# =========================================================


def test_recommendation_is_grounded_in_the_real_evidence(real_evidence) -> None:
    from agent.services.recommendation_service import RecommendationService
    from agent.strategies.catalogue import valid_strategy_ids

    result = RecommendationService(provider=None).recommend(real_evidence)

    assert result.customer_id == VERIFICATION_CUSTOMER_ID
    assert result.churn_probability == real_evidence.churn_probability
    assert result.selected_strategy.strategy_id in valid_strategy_ids()
    assert result.requires_human_approval is True

    # Every quoted SHAP value must exist in the customer's real explanation.
    real_values = {
        (driver.feature, round(driver.shap_value, 4)) for driver in real_evidence.top_drivers
    }
    for item in result.supporting_evidence:
        assert (item.feature, item.shap_value) in real_values


def test_report_renders_for_a_real_customer(real_evidence) -> None:
    from agent.cli import render_report
    from agent.services.recommendation_service import RecommendationService

    result = RecommendationService(provider=None).recommend(real_evidence)
    report = render_report(real_evidence, result)

    for heading in ["CUSTOMER", "TOP SHAP DRIVERS", "SELECTED STRATEGY", "HUMAN APPROVAL REQUIRED"]:
        assert heading in report
