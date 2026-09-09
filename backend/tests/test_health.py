"""Tests for GET /health."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_healthy_status() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_health_response_schema() -> None:
    response = client.get("/health")
    body = response.json()
    assert "status" in body
    assert isinstance(body["status"], str)


def test_health_does_not_include_database_fields() -> None:
    body = client.get("/health").json()
    dumped = str(body).lower()
    assert "database_url" not in dumped
    assert "password" not in dumped
    assert set(body.keys()) == {"status"}
