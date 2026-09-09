"""Database engine, session factory, and the FastAPI session dependency.

# ============================================================
# 1. DATABASE CONFIGURATION
# 2. ENGINE AND CONNECTION POOL
# 3. SESSION MANAGEMENT
# 7. ERROR HANDLING (rollback / dispose; HTTP mapping lives in exception handlers)
# ============================================================

The engine is created lazily on first use. Importing this module never opens a
connection, so ``GET /health`` can succeed while PostgreSQL is down. A
misconfigured production DATABASE_URL still fails at startup — that is a
configuration error, not an outage.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import Settings, get_settings
from app.db.url import is_sqlite_url

# ============================================================
# 2. ENGINE AND CONNECTION POOL
# ============================================================

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _postgres_connect_args(settings: Settings) -> dict[str, object]:
    """psycopg / psycopg2 connect arguments. SSL is opt-in via DB_SSLMODE."""
    args: dict[str, object] = {"connect_timeout": settings.db_connect_timeout}
    sslmode = settings.db_sslmode.strip()
    if sslmode:
        args["sslmode"] = sslmode
    return args


def build_engine(settings: Settings | None = None) -> Engine:
    """Create an engine from settings. Callers that need a one-off engine
    (Alembic, tests) use this; the API process uses :func:`get_engine`.
    """
    cfg = settings or get_settings()
    url = cfg.validate_database_url()
    echo = bool(cfg.db_echo) and not cfg.is_production
    engine_kwargs: dict[str, object] = {
        "echo": echo,
        "hide_parameters": True,
        "pool_pre_ping": True,
    }
    if is_sqlite_url(url):
        # FastAPI sync handlers run in a thread pool; SQLite connections must
        # be allowed to move between threads. Memory databases need StaticPool
        # so schema created on one connection is visible on the next.
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        parsed = make_url(url)
        if parsed.database in (None, "", ":memory:"):
            engine_kwargs["poolclass"] = StaticPool
    else:
        engine_kwargs["pool_size"] = cfg.db_pool_size
        engine_kwargs["max_overflow"] = cfg.db_max_overflow
        engine_kwargs["pool_timeout"] = cfg.db_pool_timeout
        engine_kwargs["pool_recycle"] = cfg.db_pool_recycle
        engine_kwargs["connect_args"] = _postgres_connect_args(cfg)
    return create_engine(url, **engine_kwargs)


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the process-wide session factory, creating it on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_engine(), autocommit=False, autoflush=False, expire_on_commit=False
        )
    return _session_factory


def reset_engine() -> None:
    """Dispose the process engine. Used on shutdown and when tests change DATABASE_URL."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def check_database_connectivity(engine: Engine | None = None) -> None:
    """Run ``SELECT 1``. Raises the driver error; callers must not leak it."""
    target = engine or get_engine()
    with target.connect() as connection:
        connection.execute(text("SELECT 1"))


# ============================================================
# 3. SESSION MANAGEMENT
# ============================================================


def get_db() -> Generator[Session, None, None]:
    """Yield a session for the lifetime of one request.

    Services commit explicitly. This dependency rolls back on an unhandled
    error and always closes the session so connections return to the pool.
    """
    session = get_session_factory()()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
