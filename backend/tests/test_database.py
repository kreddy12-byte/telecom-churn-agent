"""Database configuration, failure behaviour, and SQLite-backed persistence."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.db.init_db import create_tables
from app.db.session import reset_engine
from app.db.url import redact_database_url
from app.main import app
from tests.conftest import build_customer


def test_initial_alembic_revision_is_present() -> None:
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "0001_initial_schema.py"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    for table in ("customers", "predictions", "actions", "app_users"):
        assert table in text


def test_redact_database_url_strips_password() -> None:
    url = "postgresql+psycopg://churn_user:super-secret@db.example:5432/telecom_churn"
    redacted = redact_database_url(url)
    assert "super-secret" not in redacted
    assert "churn_user" in redacted
    assert "***" in redacted


def test_production_refuses_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./prod.db")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="refuses SQLite"):
            get_settings().validate_database_url()
    finally:
        get_settings.cache_clear()


def test_production_requires_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="DATABASE_URL is not set"):
            get_settings().validate_database_url()
    finally:
        get_settings.cache_clear()


def test_production_rejects_non_postgres_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "mysql+pymysql://u:p@localhost/db")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="PostgreSQL"):
            get_settings().validate_database_url()
    finally:
        get_settings.cache_clear()


def test_development_allows_explicit_sqlite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./local_demo.db")
    get_settings.cache_clear()
    try:
        assert get_settings().validate_database_url().startswith("sqlite:")
        assert get_settings().allows_sqlite is True
    finally:
        get_settings.cache_clear()


def test_production_create_all_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/telecom_churn"
    )
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="alembic upgrade head"):
            create_tables()
    finally:
        get_settings.cache_clear()


def test_readiness_succeeds_against_configured_sqlite() -> None:
    response = TestClient(app).get("/readiness")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_unavailable_database_does_not_leak_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "1")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://churn_user:supersecret@127.0.0.1:1/telecom_churn",
    )
    get_settings.cache_clear()
    reset_engine()
    try:
        with TestClient(app) as test_client:
            response = test_client.get("/readiness")
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "database_unavailable"
        dumped = str(body).lower()
        assert "supersecret" not in dumped
        assert "churn_user" not in dumped
        assert "127.0.0.1" not in dumped
        assert "traceback" not in dumped
        assert "database_url" not in dumped
    finally:
        get_settings.cache_clear()
        reset_engine()


def test_health_stays_up_when_database_url_points_nowhere(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DB_CONNECT_TIMEOUT", "1")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://churn_user:supersecret@127.0.0.1:1/telecom_churn",
    )
    get_settings.cache_clear()
    reset_engine()
    try:
        with TestClient(app) as test_client:
            response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
        assert "supersecret" not in response.text
    finally:
        get_settings.cache_clear()
        reset_engine()


def test_invalid_action_status_is_rejected_by_constraint(db_session) -> None:
    db_session.add(build_customer("CK-00001"))
    db_session.commit()
    from app.db.models.action import Action

    db_session.add(
        Action(
            customer_id="CK-00001",
            strategy_id="CONTRACT_CONVERSION",
            recommendation="x",
            status="NOT_A_STATUS",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
