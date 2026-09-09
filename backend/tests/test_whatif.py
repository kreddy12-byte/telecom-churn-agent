"""What-if simulation endpoint — numbers come from the locked Step 5 engine."""

from __future__ import annotations

from agent.models.scenario import WHATIF_DISCLAIMER
from tests.conftest import (
    EXPECTED_BASELINE_PROBABILITY,
    EXPECTED_BASELINE_SHAP,
    VERIFICATION_CUSTOMER_ID,
    requires_trained_model,
)


def test_whatif_missing_customer(client) -> None:
    response = client.post("/api/what-if", json={"customer_id": "0000-XXXXX"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "customer_not_found"


def test_whatif_unknown_scenario_is_rejected(client, stored_customers) -> None:
    response = client.post(
        "/api/what-if",
        json={"customer_id": "AAA0-AAAAA", "scenario_ids": ["not_a_real_scenario"]},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_scenario"


@requires_trained_model
def test_whatif_baseline_and_disclaimer(client, verification_customer) -> None:
    response = client.post(
        "/api/what-if",
        json={
            "customer_id": VERIFICATION_CUSTOMER_ID,
            "use_llm": False,
            "scenario_ids": ["two_year_contract", "annual_contract"],
        },
    )
    assert response.status_code == 200
    body = response.json()

    assert body["baseline"]["churn_probability"] == EXPECTED_BASELINE_PROBABILITY
    assert body["baseline"]["risk_level"] == "HIGH"
    assert body["requires_human_approval"] is True
    assert WHATIF_DISCLAIMER in body["limitations"]

    actual = {
        driver["feature"]: driver["shap_value"] for driver in body["baseline"]["top_drivers"]
    }
    for feature, expected in EXPECTED_BASELINE_SHAP.items():
        assert actual[feature] == expected

    assert body["scenarios"]
    assert body["recommended_scenario_id"]
    assert body["ranking_methodology"]
    scores = [scenario["ranking_score"] for scenario in body["scenarios"]]
    assert scores == sorted(scores, reverse=True)


@requires_trained_model
def test_whatif_does_not_write_predictions(client, verification_customer, db_session) -> None:
    from app.db.repositories import prediction_repository

    client.post(
        "/api/what-if",
        json={
            "customer_id": VERIFICATION_CUSTOMER_ID,
            "use_llm": False,
            "scenario_ids": ["two_year_contract"],
        },
    )
    assert prediction_repository.count_predictions(db_session, VERIFICATION_CUSTOMER_ID) == 0
