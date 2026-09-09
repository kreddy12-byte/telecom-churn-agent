"""SHAP explanation endpoint — must preserve the Step 3 contract."""

from __future__ import annotations

from tests.conftest import (
    EXPECTED_BASELINE_PROBABILITY,
    EXPECTED_BASELINE_SHAP,
    VERIFICATION_CUSTOMER_ID,
    requires_trained_model,
)


def test_explanation_missing_customer(client) -> None:
    response = client.get("/api/customers/0000-XXXXX/explanation")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "customer_not_found"


@requires_trained_model
def test_explanation_preserves_step_three_contract(client, verification_customer) -> None:
    response = client.get(f"/api/customers/{VERIFICATION_CUSTOMER_ID}/explanation")
    assert response.status_code == 200
    body = response.json()

    assert body["customer_id"] == VERIFICATION_CUSTOMER_ID
    assert body["churn_probability"] == EXPECTED_BASELINE_PROBABILITY
    assert body["risk_level"] == "HIGH"
    assert body["explained_output"] == "log_odds"
    assert isinstance(body["base_value"], float)
    assert body["model_version"]

    actual = {driver["feature"]: driver["shap_value"] for driver in body["top_drivers"]}
    for feature, expected in EXPECTED_BASELINE_SHAP.items():
        assert actual[feature] == expected

    for driver in body["top_drivers"]:
        assert driver["direction"] in {"increases_risk", "decreases_risk"}
        assert 0.0 <= driver["impact"] <= 1.0


@requires_trained_model
def test_explanation_top_k(client, verification_customer) -> None:
    response = client.get(
        f"/api/customers/{VERIFICATION_CUSTOMER_ID}/explanation", params={"top_k": 3}
    )
    assert response.status_code == 200
    assert len(response.json()["top_drivers"]) == 3


@requires_trained_model
def test_global_importance_reads_stored_artifact(client) -> None:
    response = client.get("/api/explanations/global-importance")
    assert response.status_code == 200
    body = response.json()
    assert body["explained_output"] == "log_odds"
    assert 1 <= len(body["drivers"]) <= 8
    assert body["drivers"][0]["feature"] == "tenure"
    magnitudes = [row["mean_absolute_shap"] for row in body["drivers"]]
    assert magnitudes == sorted(magnitudes, reverse=True)
    dumped = str(body).lower()
    assert "c:\\" not in dumped
    assert "joblib" not in dumped


def test_global_importance_reports_missing_artifact(client, monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        "app.services.explanation_service.models_dir", lambda: tmp_path
    )
    monkeypatch.setattr(
        "app.services.explanation_service.ml_config.MODELS_DIR", tmp_path
    )
    response = client.get("/api/explanations/global-importance")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "model_unavailable"
