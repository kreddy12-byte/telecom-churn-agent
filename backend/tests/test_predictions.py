"""Prediction endpoint and persistence."""

from __future__ import annotations

from app.db.repositories import prediction_repository
from tests.conftest import (
    EXPECTED_BASELINE_PROBABILITY,
    VERIFICATION_CUSTOMER_ID,
    requires_trained_model,
)


def test_predict_missing_customer(client) -> None:
    response = client.post("/api/predict", json={"customer_id": "0000-XXXXX"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "customer_not_found"


def test_predict_rejects_empty_customer_id(client) -> None:
    response = client.post("/api/predict", json={"customer_id": ""})
    assert response.status_code == 422


@requires_trained_model
def test_predict_verification_customer(client, verification_customer, db_session) -> None:
    response = client.post("/api/predict", json={"customer_id": VERIFICATION_CUSTOMER_ID})
    assert response.status_code == 200
    body = response.json()

    assert body["customer_id"] == VERIFICATION_CUSTOMER_ID
    assert body["churn_probability"] == EXPECTED_BASELINE_PROBABILITY
    assert body["risk_level"] == "HIGH"
    assert body["prediction"] == 1
    assert body["model_version"]
    assert body["top_drivers"]
    assert body["predicted_at"] is not None

    stored = prediction_repository.latest_for_customer(db_session, VERIFICATION_CUSTOMER_ID)
    assert stored is not None
    assert stored.churn_probability == EXPECTED_BASELINE_PROBABILITY
    assert stored.risk_level == "HIGH"
    assert stored.model_version == body["model_version"]


@requires_trained_model
def test_predictions_are_appended_not_overwritten(
    client, verification_customer, db_session
) -> None:
    first = client.post("/api/predict", json={"customer_id": VERIFICATION_CUSTOMER_ID})
    second = client.post("/api/predict", json={"customer_id": VERIFICATION_CUSTOMER_ID})
    assert first.status_code == 200
    assert second.status_code == 200

    count = prediction_repository.count_predictions(db_session, VERIFICATION_CUSTOMER_ID)
    assert count == 2
    assert first.json()["churn_probability"] == second.json()["churn_probability"]


@requires_trained_model
def test_customer_detail_includes_latest_prediction(
    client, verification_customer
) -> None:
    client.post("/api/predict", json={"customer_id": VERIFICATION_CUSTOMER_ID})
    detail = client.get(f"/api/customers/{VERIFICATION_CUSTOMER_ID}")
    assert detail.status_code == 200
    latest = detail.json()["latest_prediction"]
    assert latest is not None
    assert latest["churn_probability"] == EXPECTED_BASELINE_PROBABILITY
    assert latest["risk_level"] == "HIGH"
