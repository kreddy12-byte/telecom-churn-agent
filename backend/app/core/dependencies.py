"""FastAPI dependencies shared by the route modules.

Route handlers receive ready-to-use collaborators from here. In particular the
LLM provider is built once, from environment variables, and injected — so no
route handler ever reads, holds, or logs an API key.
"""

from __future__ import annotations

from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.orm import Session

from agent.providers.base import LLMProvider
from agent.providers.llm_provider import build_provider
from app.core.auth import (
    AuthenticatedUser,
    get_authenticated_identity,
    get_authenticated_user,
)
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.db.session import get_db

logger = get_logger(__name__)


# =========================================================
# 1. SETTINGS AND DATABASE
# =========================================================


def get_app_settings() -> Settings:
    """Provide application settings to route handlers."""
    return get_settings()


def get_db_session() -> Generator[Session, None, None]:
    """Provide a request-scoped database session."""
    yield from get_db()


# =========================================================
# 2. LLM PROVIDER
# =========================================================


@lru_cache
def _cached_provider() -> LLMProvider | None:
    """Build the provider once per process.

    ``None`` is a valid, supported result: with no LLM configured the agent runs
    on its deterministic engine and still returns complete recommendations.
    """
    try:
        provider = build_provider()
    except ValueError as exc:
        # A misconfigured provider name must not take the API down; the agent
        # degrades to deterministic output and the reason is logged once.
        logger.warning("LLM provider disabled: %s", exc)
        return None

    logger.info("LLM provider: %s", provider.name if provider else "none (deterministic engine)")
    return provider


def get_llm_provider() -> LLMProvider | None:
    """Provide the configured LLM provider, or None when the LLM is disabled."""
    return _cached_provider()


# =========================================================
# 3. PAGINATION
# =========================================================


class Pagination:
    """Validated ``limit``/``offset`` pair for list endpoints."""

    def __init__(self, limit: int, offset: int) -> None:
        self.limit = limit
        self.offset = offset


def get_pagination(
    limit: Annotated[
        int, Query(ge=1, le=100, description="Maximum number of records to return.")
    ] = 20,
    offset: Annotated[int, Query(ge=0, description="Number of records to skip.")] = 0,
) -> Pagination:
    """Parse and bound pagination query parameters.

    The upper bound is enforced by FastAPI itself, so an oversized page is
    rejected before any query runs.
    """
    return Pagination(limit=limit, offset=offset)


SettingsDep = Annotated[Settings, Depends(get_app_settings)]
SessionDep = Annotated[Session, Depends(get_db_session)]
ProviderDep = Annotated[LLMProvider | None, Depends(get_llm_provider)]
PaginationDep = Annotated[Pagination, Depends(get_pagination)]
AuthenticatedUserDep = Annotated[AuthenticatedUser, Depends(get_authenticated_user)]
AuthenticatedIdentityDep = Annotated[AuthenticatedUser, Depends(get_authenticated_identity)]
