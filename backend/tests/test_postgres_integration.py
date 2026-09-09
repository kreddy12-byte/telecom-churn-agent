"""Optional live PostgreSQL checks. Skipped when Docker/Postgres is unavailable.

These tests never invent a passing result. If PostgreSQL cannot be reached,
pytest records a skip rather than a fake pass.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

from app.db.url import is_postgresql_url, redact_database_url


def _postgres_url() -> str | None:
    url = (os.environ.get("POSTGRES_TEST_URL") or os.environ.get("DATABASE_URL") or "").strip()
    if url and is_postgresql_url(url):
        return url
    user = os.environ.get("POSTGRES_USER", "churn_user")
    password = os.environ.get("POSTGRES_PASSWORD", "churn_password")
    host = os.environ.get("POSTGRES_HOST", "127.0.0.1")
    port = os.environ.get("POSTGRES_PORT", "5432")
    database = os.environ.get("POSTGRES_DB", "telecom_churn")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{database}"


def _can_connect(url: str) -> bool:
    engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 2})
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except OperationalError:
        return False
    except Exception:
        return False
    finally:
        engine.dispose()


@pytest.fixture(scope="module")
def postgres_url() -> str:
    url = _postgres_url()
    if not url or not _can_connect(url):
        pytest.skip(
            "PostgreSQL integration could not be runtime verified because "
            "PostgreSQL/Docker is unavailable."
        )
    return url


def test_postgres_accepts_select(postgres_url: str) -> None:
    engine = create_engine(postgres_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            value = connection.execute(text("SELECT 1")).scalar()
        assert value == 1
    finally:
        engine.dispose()


def test_postgres_url_is_not_sqlite(postgres_url: str) -> None:
    assert is_postgresql_url(postgres_url)
    redacted = redact_database_url(postgres_url)
    engine = create_engine(postgres_url)
    try:
        secret = engine.url.password
        if secret:
            assert secret not in redacted
    finally:
        engine.dispose()


def test_dashboard_prediction_reads_use_existing_rows_only(postgres_url: str) -> None:
    """Summary and ranking must load against live PostgreSQL without writing.

    The Overview page fails if these queries raise. This is a read of the
    current prediction history — it must not insert a batch snapshot.
    """
    from sqlalchemy.orm import Session

    from app.db.repositories import prediction_repository
    from app.services import batch_scoring_service

    engine = create_engine(postgres_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            customer_count = session.scalar(text("SELECT COUNT(*) FROM customers"))
            prediction_count_before = session.scalar(text("SELECT COUNT(*) FROM predictions"))
            assert int(customer_count or 0) == 7043

            summary = batch_scoring_service.summarize_latest_predictions(session)
            ranking = batch_scoring_service.rank_latest_predictions(
                session, risk="HIGH", limit=10, offset=0
            )

            assert summary.total_scored >= 0
            assert set(summary.risk_counts.model_dump()) == {"HIGH", "MEDIUM", "LOW"}
            assert ranking.meta.limit == 10
            assert len(ranking.items) <= 10
            for item in ranking.items:
                assert item.risk_level == "HIGH"
                assert 0.0 <= item.churn_probability <= 1.0

            prediction_count_after = prediction_repository.count_predictions(session)
            assert prediction_count_after == int(prediction_count_before or 0)
    finally:
        engine.dispose()


def test_alembic_schema_matches_models_when_migrated(postgres_url: str) -> None:
    """If the database was migrated, expected tables exist. Skip if empty."""
    engine = create_engine(postgres_url, pool_pre_ping=True)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()
    if not tables:
        pytest.skip("PostgreSQL is reachable but has no migrated schema yet.")
    for name in ("customers", "predictions", "actions", "app_users"):
        assert name in tables
