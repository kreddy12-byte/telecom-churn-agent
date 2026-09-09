"""End-to-end backend flow for the locked verification customer 7590-VHVEG.

Customer → predict → explain → recommend → what-if → action → approve.

Skipped automatically when the trained artifacts or the raw dataset are absent.
"""

from __future__ import annotations

from agent.models.scenario import WHATIF_DISCLAIMER
from tests.conftest import (
    EXPECTED_BASELINE_PROBABILITY,
    EXPECTED_BASELINE_SHAP,
    VERIFICATION_CUSTOMER_ID,
    requires_trained_model,
)

pytestmark = requires_trained_model


def test_full_backend_flow_for_verification_customer(
    client, verification_customer, db_session, monkeypatch
) -> None:
    # Guardrail: approving an action must not call anything outside the process.
    monkeypatch.setattr(
        "app.services.action_service.logger.info",
        lambda *args, **kwargs: None,
    )

    # --------------------------------------------------------
    # 1. GET customer
    # --------------------------------------------------------
    customer = client.get(f"/api/customers/{VERIFICATION_CUSTOMER_ID}")
    assert customer.status_code == 200
    assert customer.json()["customer_id"] == VERIFICATION_CUSTOMER_ID
    assert customer.json()["contract"] == "Month-to-month"
    assert customer.json()["tenure"] == 1

    # --------------------------------------------------------
    # 2. POST prediction
    # --------------------------------------------------------
    prediction = client.post("/api/predict", json={"customer_id": VERIFICATION_CUSTOMER_ID})
    assert prediction.status_code == 200
    pred_body = prediction.json()
    assert pred_body["churn_probability"] == EXPECTED_BASELINE_PROBABILITY
    assert pred_body["risk_level"] == "HIGH"
    assert pred_body["model_version"]

    # --------------------------------------------------------
    # 3. GET explanation
    # --------------------------------------------------------
    explanation = client.get(f"/api/customers/{VERIFICATION_CUSTOMER_ID}/explanation")
    assert explanation.status_code == 200
    expl_body = explanation.json()
    assert expl_body["explained_output"] == "log_odds"
    assert expl_body["churn_probability"] == EXPECTED_BASELINE_PROBABILITY
    actual_shap = {d["feature"]: d["shap_value"] for d in expl_body["top_drivers"]}
    for feature, expected in EXPECTED_BASELINE_SHAP.items():
        assert actual_shap[feature] == expected

    # --------------------------------------------------------
    # 4. POST recommendation
    # --------------------------------------------------------
    recommendation = client.post(
        "/api/recommendation",
        json={"customer_id": VERIFICATION_CUSTOMER_ID, "detailed": True},
    )
    assert recommendation.status_code == 200
    rec_body = recommendation.json()
    assert rec_body["requires_human_approval"] is True
    assert rec_body["churn_probability"] == EXPECTED_BASELINE_PROBABILITY
    strategy_id = rec_body["selected_strategy"]["strategy_id"]
    rec_text = rec_body["recommendation"]

    # --------------------------------------------------------
    # 5. POST what-if
    # --------------------------------------------------------
    whatif = client.post(
        "/api/what-if",
        json={"customer_id": VERIFICATION_CUSTOMER_ID, "use_llm": False},
    )
    assert whatif.status_code == 200
    whatif_body = whatif.json()
    assert whatif_body["baseline"]["churn_probability"] == EXPECTED_BASELINE_PROBABILITY
    assert WHATIF_DISCLAIMER in whatif_body["limitations"]
    assert whatif_body["requires_human_approval"] is True
    assert whatif_body["scenarios"]

    # --------------------------------------------------------
    # 6. POST action (PENDING)
    # --------------------------------------------------------
    created = client.post(
        "/api/actions",
        json={
            "customer_id": VERIFICATION_CUSTOMER_ID,
            "strategy_id": strategy_id,
            "recommendation": rec_text,
        },
    )
    assert created.status_code == 201
    action = created.json()
    assert action["status"] == "PENDING"
    action_id = action["id"]

    # --------------------------------------------------------
    # 7. PATCH action → APPROVED (the only way it becomes approved)
    # --------------------------------------------------------
    approved = client.patch(f"/api/actions/{action_id}", json={"status": "APPROVED"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"

    # Re-fetch to prove the decision persisted and that we did not invent a
    # second, auto-approved row along the way.
    listed = client.get("/api/actions", params={"customer_id": VERIFICATION_CUSTOMER_ID})
    assert listed.json()["meta"]["total"] == 1
    assert listed.json()["items"][0]["status"] == "APPROVED"
    assert listed.json()["items"][0]["id"] == action_id
