"""Current authenticated user."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import get_authenticated_identity
from app.core.dependencies import AuthenticatedIdentityDep
from app.schemas.auth import MeResponse

router = APIRouter(
    prefix="/me",
    tags=["auth"],
    dependencies=[Depends(get_authenticated_identity)],
)


@router.get(
    "",
    response_model=MeResponse,
    summary="Current user",
    description=(
        "Returns the identity taken from the verified Auth0 access token. "
        "A valid token is sufficient. REVIEWER/ADMIN is returned only when "
        "that claim is on the token; a missing role does not fail this request."
    ),
)
def get_me(user: AuthenticatedIdentityDep) -> MeResponse:
    return MeResponse(
        sub=user.sub,
        email=user.email,
        name=user.name,
        picture=user.picture,
        role=user.role or None,
    )
