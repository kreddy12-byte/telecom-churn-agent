"""Local application-profile orchestration.

Identity is Auth0. This service only stores a display/audit cache keyed by
``sub``. It never stores passwords or provider tokens.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.auth import AuthenticatedUser
from app.db.models.user import AppUser
from app.db.repositories import user_repository


def upsert_from_principal(session: Session, principal: AuthenticatedUser) -> AppUser:
    user = user_repository.upsert_profile(
        session,
        auth0_sub=principal.sub,
        email=principal.email,
        name=principal.name,
        picture_url=principal.picture,
        role=principal.role,
    )
    session.commit()
    return user
