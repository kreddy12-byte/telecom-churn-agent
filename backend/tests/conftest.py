"""Shared fixtures for backend tests.

The HTTP tests run against an in-memory SQLite database so they do not need
PostgreSQL. Tests that call the trained model skip themselves when the artifacts
or the raw dataset are missing — they never invent a probability.
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator

# Isolated test database. Must be set before importing the application so
# Settings and lifespan see an explicit SQLite URL — never a silent fallback.
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.project_path import ensure_project_root_on_path

ensure_project_root_on_path()

from agent.providers.base import LLMCompletion, LLMProvider  # noqa: E402
from app.core.auth import (  # noqa: E402
    ROLE_REVIEWER,
    AuthenticatedUser,
    get_authenticated_identity,
    get_authenticated_user,
)
from app.core.dependencies import get_db_session, get_llm_provider  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import AppUser, Customer  # noqa: F401, E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from ml.src import config as ml_config  # noqa: E402

# ============================================================
# 1. VERIFICATION CUSTOMER AND ARTIFACT GATES
# ============================================================

VERIFICATION_CUSTOMER_ID = "7590-VHVEG"
EXPECTED_BASELINE_PROBABILITY = 0.8064
EXPECTED_BASELINE_SHAP = {
    "tenure": 1.3752,
    "MonthlyCharges": 0.7998,
    "InternetService": -0.6895,
    "TotalCharges": -0.4549,
    "Contract": 0.4077,
}

REQUIRED_ML_ARTIFACTS = [
    ml_config.MODELS_DIR / ml_config.BEST_MODEL_FILENAME,
    ml_config.MODELS_DIR / ml_config.PREPROCESSOR_FILENAME,
    ml_config.MODELS_DIR / ml_config.METADATA_FILENAME,
    ml_config.RAW_DATA_DIR / ml_config.RAW_DATASET_FILENAME,
]

requires_trained_model = pytest.mark.skipif(
    not all(path.exists() for path in REQUIRED_ML_ARTIFACTS),
    reason="Trained model artifacts or raw dataset not available; run the ML pipeline first.",
)


# ============================================================
# 2. STUB LLM PROVIDER (NO NETWORK, NO PAID CALLS)
# ============================================================


class StubProvider(LLMProvider):
    """Returns canned text instead of calling an LLM API."""

    name = "stub"

    def __init__(self, response_text: str = "", model: str = "stub-model") -> None:
        self.response_text = response_text
        self.model = model
        self.calls: list[tuple[str, str]] = []

    def is_available(self) -> bool:
        return True

    def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        self.calls.append((system_prompt, user_prompt))
        return LLMCompletion(text=self.response_text, model=self.model, provider=self.name)


def make_recommendation_llm_payload(strategy_id: str = "EARLY_LIFECYCLE_ONBOARDING") -> str:
    """A well-formed agent reply that names a real catalogue strategy."""
    return json.dumps(
        {
            "strategy_id": strategy_id,
            "recommendation": (
                "Arrange a personalised onboarding review for this recently joined "
                "customer and walk them through the services in their plan. A human "
                "must approve contact before anything is sent."
            ),
            "reasoning": [
                "The model estimates a high churn probability for this customer.",
                "Short tenure is the strongest risk-increasing driver in the explanation.",
            ],
        }
    )


# ============================================================
# 3. DATABASE
# ============================================================


@pytest.fixture()
def db_engine():
    """In-memory SQLite shared across threads (TestClient runs the app in a thread)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite does not enforce FOREIGN KEY constraints unless asked.
    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine) -> Generator[Session, None, None]:
    factory = sessionmaker(
        bind=db_engine, autocommit=False, autoflush=False, expire_on_commit=False
    )
    session = factory()
    try:
        yield session
    finally:
        session.close()


TEST_REVIEWER = AuthenticatedUser(
    sub="auth0|test-reviewer",
    email="reviewer@example.test",
    name="Test Reviewer",
    picture=None,
    role=ROLE_REVIEWER,
    roles=(ROLE_REVIEWER,),
)


def _override_authenticated_user() -> AuthenticatedUser:
    return TEST_REVIEWER


@pytest.fixture()
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """API client bound to the in-memory database, with the LLM disabled."""

    def _override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_llm_provider] = lambda: None
    app.dependency_overrides[get_authenticated_user] = _override_authenticated_user
    app.dependency_overrides[get_authenticated_identity] = _override_authenticated_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def stub_provider() -> StubProvider:
    return StubProvider(response_text=make_recommendation_llm_payload())


@pytest.fixture()
def client_with_stub_llm(
    db_session: Session, stub_provider: StubProvider
) -> Generator[TestClient, None, None]:
    def _override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_llm_provider] = lambda: stub_provider
    app.dependency_overrides[get_authenticated_user] = _override_authenticated_user
    app.dependency_overrides[get_authenticated_identity] = _override_authenticated_user
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


# ============================================================
# 5. CUSTOMER FIXTURES
# ============================================================


def build_customer(customer_id: str, **overrides: object) -> Customer:
    """A Telco-shaped customer row. Extra kwargs override individual fields."""
    fields = {
        "customer_id": customer_id,
        "gender": "Female",
        "senior_citizen": 0,
        "partner": "Yes",
        "dependents": "No",
        "tenure": 12,
        "phone_service": "Yes",
        "multiple_lines": "No",
        "internet_service": "DSL",
        "online_security": "No",
        "online_backup": "No",
        "device_protection": "No",
        "tech_support": "No",
        "streaming_tv": "No",
        "streaming_movies": "No",
        "contract": "Month-to-month",
        "paperless_billing": "Yes",
        "payment_method": "Electronic check",
        "monthly_charges": 45.0,
        "total_charges": 540.0,
    }
    fields.update(overrides)
    return Customer(**fields)


@pytest.fixture()
def stored_customers(db_session: Session) -> list[Customer]:
    """Three customers for list/pagination tests. No model inference involved."""
    customers = [
        build_customer("AAA0-AAAAA", tenure=1),
        build_customer("BBB0-BBBBB", tenure=24, contract="One year"),
        build_customer("CCC0-CCCCC", tenure=60, contract="Two year"),
    ]
    db_session.add_all(customers)
    db_session.commit()
    return customers


@pytest.fixture()
def verification_customer(db_session: Session) -> Customer:
    """The real 7590-VHVEG record from the dataset, stored in the test database."""
    from ml.src.prediction.predictor import load_customer_from_dataset

    record = load_customer_from_dataset(row=None, customer_id=VERIFICATION_CUSTOMER_ID)
    customer = Customer.from_dataset_record(record)
    db_session.add(customer)
    db_session.commit()
    return customer
