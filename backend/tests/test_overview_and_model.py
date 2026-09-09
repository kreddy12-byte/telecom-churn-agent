"""Overview aggregates and public model metadata."""

from __future__ import annotations

from app.db.repositories import action_repository, prediction_repository
from tests.conftest import build_customer


def test_overview_counts_are_derived_from_stored_rows(client, db_session) -> None:
    db_session.add_all(
        [build_customer("OVW-00001"), build_customer("OVW-00002"), build_customer("OVW-00003")]
    )
    db_session.commit()
    prediction_repository.create_prediction(db_session, "OVW-00001", 0.81, "HIGH", "1.0.0")
    prediction_repository.create_prediction(db_session, "OVW-00002", 0.22, "LOW", "1.0.0")
    action_repository.create_action(
        db_session, "OVW-00001", "CONTRACT_CONVERSION", "Review the contract."
    )
    db_session.commit()

    response = client.get("/api/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["customer_count"] == 3
    assert body["evaluated_count"] == 2
    assert body["risk_counts"]["HIGH"] == 1
    assert body["risk_counts"]["LOW"] == 1
    assert body["action_counts"]["PENDING"] == 1
    assert body["recent_high_risk"][0]["customer_id"] == "OVW-00001"


def test_model_info_omits_paths_and_exposes_real_metrics(client) -> None:
    response = client.get("/api/model")
    assert response.status_code == 200
    body = response.json()
    assert body["model_name"] == "LogisticRegression"
    assert body["model_version"] == "1.0.0"
    assert body["explainability"] == "SHAP LinearExplainer"
    assert body["explained_output"] == "log_odds"
    assert "accuracy" in body["metrics"]
    dumped = str(body).lower()
    assert "c:\\" not in dumped
    assert "api_key" not in dumped
    assert "dataset_path" not in dumped
