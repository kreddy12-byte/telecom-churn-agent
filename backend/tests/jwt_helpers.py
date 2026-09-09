"""Helpers for minting RS256 JWTs in authentication tests.

These keys exist only in the test process. They are not Auth0 credentials.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from functools import lru_cache

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

AUTH0_DOMAIN = "test.auth0.com"
AUTH0_AUDIENCE = "https://api.retention-intelligence.test"
AUTH0_ISSUER = "https://test.auth0.com/"
ROLES_CLAIM = "https://retention-intelligence.app/roles"


@lru_cache
def _rsa_pair() -> tuple[object, object]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def private_key():
    return _rsa_pair()[0]


def public_key():
    return _rsa_pair()[1]


class FakeJWKClient:
    """Returns the test public key regardless of kid. Never talks to Auth0."""

    def __init__(self, key=None) -> None:
        self.key = key or public_key()

    def get_signing_key_from_jwt(self, _token: str):
        return type("SigningKey", (), {"key": self.key})()


def mint_token(
    *,
    sub: str = "auth0|reviewer-1",
    email: str | None = "reviewer@example.test",
    name: str | None = "Ada Reviewer",
    roles: list[str] | None = None,
    audience: str = AUTH0_AUDIENCE,
    issuer: str = AUTH0_ISSUER,
    expires_in: int = 3600,
    extra: dict | None = None,
    key=None,
    algorithm: str = "RS256",
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "iss": issuer,
        "aud": audience,
        "iat": now,
        "exp": now + timedelta(seconds=expires_in),
    }
    if email is not None:
        payload["email"] = email
    if name is not None:
        payload["name"] = name
    if roles is not None:
        payload[ROLES_CLAIM] = roles
    if extra:
        payload.update(extra)
    signing_key = key if key is not None else ("hmac-not-used" if algorithm == "HS256" else private_key())
    return jwt.encode(payload, signing_key, algorithm=algorithm)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
