"""Authenticated current-user contract."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MeResponse(BaseModel):
    """Backend-verified identity for the signed-in user."""

    sub: str = Field(..., description="Auth0 subject. Stable external identity key.")
    email: str | None = None
    name: str | None = None
    picture: str | None = None
    role: str | None = Field(
        default=None,
        description=(
            "ADMIN or REVIEWER from the verified access token. "
            "Null when the user is authenticated but has no application role."
        ),
    )
