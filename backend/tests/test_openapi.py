"""OpenAPI, health, and error-envelope checks that do not need the ML stack."""

from __future__ import annotations


def test_health_still_returns_healthy_status(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_openapi_documents_the_phase_six_surface(client) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    paths = spec["paths"]

    for path in [
        "/health",
        "/readiness",
        "/api/customers",
        "/api/customers/{customer_id}",
        "/api/customers/{customer_id}/explanation",
        "/api/predict",
        "/api/predictions/batch",
        "/api/predictions/ranking",
        "/api/predictions/summary",
        "/api/predictions/distribution",
        "/api/explanations/global-importance",
        "/api/recommendation",
        "/api/what-if",
        "/api/actions",
        "/api/actions/{action_id}",
        "/api/overview",
        "/api/model",
        "/api/me",
    ]:
        assert path in paths, f"missing {path}"

    whatif = spec["paths"]["/api/what-if"]["post"]["description"]
    assert "not causal" in whatif.lower() or "not a causal" in whatif.lower()

    # Dashboard load depends on these being registered. A stale process that
    # only has /api/overview will 404 here and the Overview page fails closed.
    assert "get" in spec["paths"]["/api/predictions/summary"]
    assert "get" in spec["paths"]["/api/predictions/ranking"]
    assert "post" in spec["paths"]["/api/predictions/batch"]
    assert "get" in spec["paths"]["/api/predictions/distribution"]
    assert "get" in spec["paths"]["/api/explanations/global-importance"]


def test_docs_ui_loads(client) -> None:
    response = client.get("/docs")
    assert response.status_code == 200


def test_error_envelope_does_not_leak_internals(client) -> None:
    response = client.get("/api/customers/no-such-customer")
    assert response.status_code == 404
    body = response.json()
    assert set(body["error"].keys()) == {"code", "message", "details"}
    dumped = str(body).lower()
    assert "traceback" not in dumped
    assert "postgresql" not in dumped
    assert "api_key" not in dumped
    assert "authorization" not in dumped
