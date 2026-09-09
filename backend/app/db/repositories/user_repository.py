"""Data access for local application profiles."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user import AppUser


def get_by_sub(session: Session, auth0_sub: str) -> AppUser | None:
    return session.scalar(select(AppUser).where(AppUser.auth0_sub == auth0_sub))


def upsert_profile(
    session: Session,
    *,
    auth0_sub: str,
    email: str | None,
    name: str | None,
    picture_url: str | None,
    role: str,
) -> AppUser:
    """Create or refresh the local profile for an Auth0 subject."""
    user = get_by_sub(session, auth0_sub)
    now = datetime.now(timezone.utc)
    if user is None:
        user = AppUser(
            auth0_sub=auth0_sub,
            email=email,
            name=name,
            picture_url=picture_url,
            role=role,
            last_seen_at=now,
        )
        session.add(user)
    else:
        user.email = email or user.email
        user.name = name or user.name
        user.picture_url = picture_url or user.picture_url
        user.role = role
        user.last_seen_at = now
    session.flush()
    return user
