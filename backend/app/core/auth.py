"""Authenticated principal extraction.

Identity comes from a verified Auth0 access token — never from a request body,
query parameter, or frontend-supplied header. Application roles, when present
on the token, are informational (TopBar badge). They are not fabricated and
they are not required to use the product.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token, extract_bearer_token
from app.db.session import get_db

ROLE_ADMIN = "ADMIN"
ROLE_REVIEWER = "REVIEWER"
ALLOWED_ROLES = frozenset({ROLE_ADMIN, ROLE_REVIEWER})


# ============================================================
# 1. AUTHENTICATION CONFIGURATION
# ============================================================


@dataclass(frozen=True)
class AuthenticatedUser:
    """Verified identity for the current request.

    ``role`` is ADMIN or REVIEWER when that claim is on the access token;
    otherwise it is empty. ``sub`` is the Auth0 subject.
    """

    sub: str
    email: str | None
    name: str | None
    picture: str | None
    role: str
    roles: tuple[str, ...]


# ============================================================
# 2. ROLE EXTRACTION
# ============================================================


def _claim_list(payload: dict[str, Any], claim: str) -> list[str]:
    raw = payload.get(claim)
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, (list, tuple)):
        return [item for item in raw if isinstance(item, str)]
    return []


def roles_from_claims(payload: dict[str, Any], roles_claim: str) -> list[str]:
    """Read application roles from a verified access-token payload."""
    values = _claim_list(payload, roles_claim)
    if not values:
        values = _claim_list(payload, "roles")
    normalized: list[str] = []
    for value in values:
        role = value.strip().upper()
        if role in ALLOWED_ROLES and role not in normalized:
            normalized.append(role)
    return normalized


def token_application_role(roles: list[str]) -> str:
    """ADMIN or REVIEWER from the token only. Empty means no verified application role."""
    if ROLE_ADMIN in roles:
        return ROLE_ADMIN
    if ROLE_REVIEWER in roles:
        return ROLE_REVIEWER
    return ""


def principal_from_claims(payload: dict[str, Any], settings: Settings) -> AuthenticatedUser:
    """Build the request principal from verified claims (no DB)."""
    roles = roles_from_claims(payload, settings.auth0_roles_claim)
    role = token_application_role(roles)
    email = payload.get("email") or payload.get(f"{settings.auth0_roles_claim.rsplit('/', 1)[0]}/email")
    name = payload.get("name")
    picture = payload.get("picture")
    if not isinstance(email, str):
        email = None
    if not isinstance(name, str):
        name = None
    if not isinstance(picture, str):
        picture = None
    return AuthenticatedUser(
        sub=payload["sub"],
        email=email,
        name=name,
        picture=picture,
        role=role,
        roles=tuple(roles),
    )


# ============================================================
# 3. AUTHORIZATION
# ============================================================


def _principal_from_request(
    request: Request,
    session: Session,
    settings: Settings,
) -> AuthenticatedUser:
    token = extract_bearer_token(request.headers.get("authorization"))
    claims = decode_access_token(token, settings)
    principal = principal_from_claims(claims, settings)
    from app.services import user_service

    user_service.upsert_from_principal(session, principal)
    return principal


def get_authenticated_identity(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser:
    """Valid access token is enough. A missing role is not an error."""
    return _principal_from_request(request, session, settings)


def get_authenticated_user(
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedUser:
    """FastAPI dependency: validate the Auth0 bearer token. Role is not required."""
    return _principal_from_request(request, session, settings)


# ============================================================
# 4. ERROR HANDLING
# ============================================================
# Missing/invalid tokens raise UnauthenticatedError (401).
# Messages stay generic so JWT internals never leak.
