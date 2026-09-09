"""JWT access-token validation for Auth0-issued bearer tokens.

The frontend identity is never trusted. Protected endpoints accept a bearer
token, then this module independently checks signature, issuer, audience, and
expiry against Auth0's JWKS. Validation failures are logged without the token
or the Authorization header.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError

from app.core.config import Settings
from app.core.errors import UnauthenticatedError
from app.core.logging import get_logger

logger = get_logger(__name__)

# Auth0 access tokens for SPAs are RS256. HS256 / "none" are rejected by
# pinning the algorithm list — unsigned or shared-secret tokens never verify.
_ALLOWED_ALGORITHMS = ["RS256"]


# ============================================================
# 1. AUTHENTICATION CONFIGURATION
# ============================================================


@lru_cache
def get_jwks_client(domain: str) -> PyJWKClient:
    """Cached JWKS client for an Auth0 domain. Domain is not a secret."""
    return PyJWKClient(f"https://{domain}/.well-known/jwks.json")


# ============================================================
# 2. TOKEN VALIDATION
# ============================================================


def extract_bearer_token(authorization: str | None) -> str:
    """Return the raw JWT from an Authorization header, or raise 401.

    The header value is never logged.
    """
    if not authorization:
        raise UnauthenticatedError()
    scheme, _, credential = authorization.partition(" ")
    if scheme.lower() != "bearer" or not credential.strip():
        raise UnauthenticatedError()
    return credential.strip()


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Validate an Auth0 access token and return its claims.

    Raises UnauthenticatedError for any failure. The token itself is not
    included in logs or error payloads.
    """
    if not settings.auth0_domain or not settings.auth0_audience or not settings.auth0_issuer_url:
        logger.error("Auth0 is not configured; refusing authenticated requests.")
        raise UnauthenticatedError()

    try:
        signing_key = get_jwks_client(settings.auth0_domain).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALLOWED_ALGORITHMS,
            audience=settings.auth0_audience,
            issuer=settings.auth0_issuer_url,
            options={
                "require": ["exp", "iss", "aud", "sub"],
                "verify_signature": True,
                "verify_exp": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
    except InvalidTokenError:
        # 3. ERROR HANDLING — generic 401 only. Do not log the token, JWKS,
        # algorithm, issuer, or audience so internals never leak to clients.
        logger.warning("Access token validation failed.")
        raise UnauthenticatedError() from None
    except UnauthenticatedError:
        raise
    except Exception:
        logger.warning("Access token validation failed.")
        raise UnauthenticatedError() from None

    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise UnauthenticatedError()
    return claims
