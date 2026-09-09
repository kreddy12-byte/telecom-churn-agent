"""Auth0 JWT validation and action-audit identity."""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.auth import (
    ROLE_ADMIN,
    ROLE_REVIEWER,
    get_authenticated_identity,
    get_authenticated_user,
)
from app.core.config import get_settings
from app.core.dependencies import get_db_session, get_llm_provider
from app.db.session import get_db
from app.main import app
from tests.conftest import TEST_REVIEWER
from tests.jwt_helpers import (
    AUTH0_AUDIENCE,
    AUTH0_DOMAIN,
    AUTH0_ISSUER,
    ROLES_CLAIM,
    FakeJWKClient,
    auth_header,
    mint_token,
    public_key,
)


@pytest.fixture()
def auth0_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTH0_DOMAIN", AUTH0_DOMAIN)
    monkeypatch.setenv("AUTH0_AUDIENCE", AUTH0_AUDIENCE)
    monkeypatch.setenv("AUTH0_ISSUER", AUTH0_ISSUER)
    get_settings.cache_clear()
    monkeypatch.setattr(
        "app.core.security.get_jwks_client",
        lambda _domain: FakeJWKClient(public_key()),
    )
    yield
    get_settings.cache_clear()


@pytest.fixture()
def jwt_client(
    db_session: Session, auth0_settings: None
) -> Generator[TestClient, None, None]:
    """HTTP client that validates real RS256 JWTs. No identity override."""

    def _override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_llm_provider] = lambda: None
    app.dependency_overrides.pop(get_authenticated_user, None)
    app.dependency_overrides.pop(get_authenticated_identity, None)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_health_allows_missing_jwt() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/overview"),
        ("post", "/api/predictions/batch"),
        ("get", "/api/predictions/ranking"),
        ("get", "/api/predictions/summary"),
        ("get", "/api/predictions/distribution"),
        ("get", "/api/explanations/global-importance"),
    ],
)
def test_protected_endpoint_rejects_missing_jwt(
    jwt_client: TestClient, method: str, path: str
) -> None:
    response = getattr(jwt_client, method)(path)
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthenticated"
    assert "signature" not in body["error"]["message"].lower()
    assert "issuer" not in body["error"]["message"].lower()
    assert response.headers.get("www-authenticate") == "Bearer"


def test_protected_endpoint_rejects_invalid_jwt(jwt_client: TestClient) -> None:
    response = jwt_client.get(
        "/api/overview", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_protected_endpoint_rejects_expired_jwt(jwt_client: TestClient) -> None:
    token = mint_token(roles=[ROLE_REVIEWER], expires_in=-30)
    response = jwt_client.get("/api/overview", headers=auth_header(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_protected_endpoint_rejects_invalid_issuer(jwt_client: TestClient) -> None:
    token = mint_token(roles=[ROLE_REVIEWER], issuer="https://evil.example/")
    response = jwt_client.get("/api/overview", headers=auth_header(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_protected_endpoint_rejects_invalid_audience(jwt_client: TestClient) -> None:
    token = mint_token(roles=[ROLE_REVIEWER], audience="https://other-api.example")
    response = jwt_client.get("/api/overview", headers=auth_header(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_protected_endpoint_rejects_wrong_signature(jwt_client: TestClient) -> None:
    from cryptography.hazmat.primitives.asymmetric import rsa

    other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = mint_token(roles=[ROLE_REVIEWER], key=other_key)
    response = jwt_client.get("/api/overview", headers=auth_header(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_protected_endpoint_rejects_hs256_token(jwt_client: TestClient) -> None:
    token = mint_token(roles=[ROLE_REVIEWER], algorithm="HS256")
    response = jwt_client.get("/api/overview", headers=auth_header(token))
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthenticated"
    dumped = str(body).lower()
    assert "hs256" not in dumped
    assert "signing" not in dumped


def test_valid_reviewer_can_read_overview(jwt_client: TestClient) -> None:
    token = mint_token(roles=[ROLE_REVIEWER])
    response = jwt_client.get("/api/overview", headers=auth_header(token))
    assert response.status_code == 200
    assert "customer_count" in response.json()


def test_valid_reviewer_can_read_prediction_summary(jwt_client: TestClient) -> None:
    token = mint_token(roles=[ROLE_REVIEWER])
    response = jwt_client.get("/api/predictions/summary", headers=auth_header(token))
    assert response.status_code == 200
    assert response.status_code != 404
    body = response.json()
    assert body["total_scored"] == 0
    assert body["risk_counts"] == {"HIGH": 0, "MEDIUM": 0, "LOW": 0}


def test_valid_reviewer_can_read_prediction_ranking(jwt_client: TestClient) -> None:
    token = mint_token(roles=[ROLE_REVIEWER])
    response = jwt_client.get(
        "/api/predictions/ranking",
        params={"risk": "HIGH", "limit": 10, "offset": 0},
        headers=auth_header(token),
    )
    assert response.status_code == 200
    assert response.status_code != 404
    body = response.json()
    assert body["items"] == []
    assert body["meta"] == {"total": 0, "limit": 10, "offset": 0}


def test_valid_admin_can_read_overview(jwt_client: TestClient) -> None:
    token = mint_token(sub="auth0|admin-1", email="admin@example.test", roles=[ROLE_ADMIN])
    response = jwt_client.get("/api/overview", headers=auth_header(token))
    assert response.status_code == 200


def test_authenticated_user_without_role_can_read_overview(jwt_client: TestClient) -> None:
    token = mint_token(sub="auth0|demo", roles=None)
    response = jwt_client.get("/api/overview", headers=auth_header(token))
    assert response.status_code == 200
    assert "customer_count" in response.json()


def test_unknown_token_role_does_not_block_the_application(jwt_client: TestClient) -> None:
    token = mint_token(roles=["VIEWER"])
    response = jwt_client.get("/api/overview", headers=auth_header(token))
    assert response.status_code == 200


def test_me_rejects_missing_jwt(jwt_client: TestClient) -> None:
    response = jwt_client.get("/api/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


def test_me_returns_verified_claims(jwt_client: TestClient) -> None:
    token = mint_token(
        sub="auth0|reviewer-9",
        email="nina@example.test",
        name="Nina Reviewer",
        roles=[ROLE_REVIEWER],
    )
    response = jwt_client.get("/api/me", headers=auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body["sub"] == "auth0|reviewer-9"
    assert body["email"] == "nina@example.test"
    assert body["name"] == "Nina Reviewer"
    assert body["role"] == ROLE_REVIEWER


def test_me_returns_null_role_for_authenticated_signup(jwt_client: TestClient) -> None:
    """A valid token without ADMIN/REVIEWER is identity, not authorization."""
    token = mint_token(
        sub="auth0|new-user",
        email="new@example.test",
        name="New User",
        roles=None,
    )
    response = jwt_client.get("/api/me", headers=auth_header(token))
    assert response.status_code == 200
    body = response.json()
    assert body["sub"] == "auth0|new-user"
    assert body["email"] == "new@example.test"
    assert body["role"] is None


def test_me_returns_admin(jwt_client: TestClient) -> None:
    token = mint_token(
        sub="auth0|admin-9",
        email="admin@example.test",
        name="Ada Admin",
        roles=[ROLE_ADMIN],
    )
    response = jwt_client.get("/api/me", headers=auth_header(token))
    assert response.status_code == 200
    assert response.json()["role"] == ROLE_ADMIN


def test_authenticated_user_without_role_can_read_reviewer_apis(jwt_client: TestClient) -> None:
    token = mint_token(sub="auth0|demo", roles=None)
    headers = auth_header(token)
    overview = jwt_client.get("/api/overview", headers=headers)
    summary = jwt_client.get("/api/predictions/summary", headers=headers)
    assert overview.status_code == 200
    assert summary.status_code == 200


def test_review_records_authenticated_identity(
    jwt_client: TestClient, stored_customers
) -> None:
    token = mint_token(
        sub="auth0|audit-user",
        email="audit@example.test",
        name="Audit User",
        roles=[ROLE_ADMIN],
    )
    created = jwt_client.post(
        "/api/actions",
        headers=auth_header(token),
        json={
            "customer_id": "AAA0-AAAAA",
            "strategy_id": "CONTRACT_CONVERSION",
            "recommendation": "Offer a longer-term contract after human review.",
        },
    )
    assert created.status_code == 201, created.text
    assert created.json()["reviewed_by_sub"] is None

    reviewed = jwt_client.patch(
        f"/api/actions/{created.json()['id']}",
        headers=auth_header(token),
        json={"status": "APPROVED"},
    )
    assert reviewed.status_code == 200, reviewed.text
    body = reviewed.json()
    assert body["status"] == "APPROVED"
    assert body["reviewed_by_sub"] == "auth0|audit-user"
    assert body["reviewed_by_email"] == "audit@example.test"
    assert body["reviewed_by_name"] == "Audit User"


def test_frontend_cannot_spoof_role_via_header(jwt_client: TestClient) -> None:
    token = mint_token(roles=[ROLE_REVIEWER])
    response = jwt_client.get(
        "/api/me",
        headers={**auth_header(token), "X-User-Role": "ADMIN"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == ROLE_REVIEWER


def test_override_client_still_authenticates_as_reviewer(client: TestClient) -> None:
    """Existing fixtures inject a reviewer so prior tests keep working."""
    response = client.get("/api/me")
    assert response.status_code == 200
    assert response.json()["sub"] == TEST_REVIEWER.sub
    assert response.json()["role"] == ROLE_REVIEWER


def test_cors_wildcard_rejected_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.cors_is_safe_for_environment() is False
    finally:
        get_settings.cache_clear()


def test_unconfigured_auth0_rejects_even_a_well_formed_token(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AUTH0_DOMAIN", "")
    monkeypatch.setenv("AUTH0_AUDIENCE", "")
    monkeypatch.setenv("AUTH0_ISSUER", "")
    get_settings.cache_clear()

    def _override_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_llm_provider] = lambda: None
    app.dependency_overrides.pop(get_authenticated_user, None)
    app.dependency_overrides.pop(get_authenticated_identity, None)
    try:
        with TestClient(app) as test_client:
            token = mint_token(roles=[ROLE_REVIEWER])
            response = test_client.get("/api/overview", headers=auth_header(token))
            assert response.status_code == 401
            assert response.json()["error"]["code"] == "unauthenticated"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_roles_from_claims_reads_namespaced_claim() -> None:
    from app.core.auth import roles_from_claims

    payload = {ROLES_CLAIM: ["REVIEWER", "admin"]}
    assert roles_from_claims(payload, ROLES_CLAIM) == ["REVIEWER", "ADMIN"]
