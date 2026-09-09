"""Recommendation endpoint. LLM calls are stubbed; none are paid."""

from __future__ import annotations

from tests.conftest import VERIFICATION_CUSTOMER_ID, requires_trained_model


def test_recommendation_missing_customer(client) -> None:
    response = client.post("/api/recommendation", json={"customer_id": "0000-XXXXX"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "customer_not_found"


@requires_trained_model
def test_recommendation_compact_contract_requires_human_approval(
    client, verification_customer
) -> None:
    response = client.post(
        "/api/recommendation", json={"customer_id": VERIFICATION_CUSTOMER_ID}
    )
    assert response.status_code == 200
    body = response.json()

    assert body["customer_id"] == VERIFICATION_CUSTOMER_ID
    assert body["recommendation"]
    assert body["reason"]
    assert body["priority"] in {"LOW", "MEDIUM", "HIGH"}
    assert body["confidence"] in {"LOW", "MEDIUM", "HIGH"}
    assert body["requires_human_approval"] is True


@requires_trained_model
def test_recommendation_detailed_preserves_agent_contract(
    client, verification_customer
) -> None:
    response = client.post(
        "/api/recommendation",
        json={"customer_id": VERIFICATION_CUSTOMER_ID, "detailed": True},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["requires_human_approval"] is True
    assert body["selected_strategy"]["strategy_id"]
    assert body["supporting_evidence"]
    assert body["objective"]
    assert body["limitations"]
    assert body["provider"] == "deterministic_fallback"
    assert body["churn_probability"] == 0.8064
    assert body["risk_level"] == "HIGH"


@requires_trained_model
def test_recommendation_with_mocked_llm(
    client_with_stub_llm, verification_customer, stub_provider
) -> None:
    response = client_with_stub_llm.post(
        "/api/recommendation",
        json={"customer_id": VERIFICATION_CUSTOMER_ID, "detailed": True},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["requires_human_approval"] is True
    assert stub_provider.calls, "the stub provider should have been invoked"
    # A successful stub still cannot override system-owned fields.
    assert body["churn_probability"] == 0.8064
    assert body["risk_level"] == "HIGH"
