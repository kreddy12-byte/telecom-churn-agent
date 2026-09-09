"""Create the database schema for local development and tests.

# ============================================================
# 6. MIGRATIONS
# ============================================================

Production schema changes go through Alembic (``alembic upgrade head``).
``Base.metadata.create_all()`` remains a convenience for SQLite tests and local
demos. It is refused when ``APP_ENV=production``.

Usage::

    python -m app.db.init_db          # development/testing only
    alembic upgrade head              # production and shared PostgreSQL
"""

from __future__ import annotations

from sqlalchemy import Engine

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import Base
from app.db.session import get_engine

# Importing the models package registers every table on Base.metadata.
import app.db.models  # noqa: F401

logger = get_logger(__name__)


def create_tables(engine: Engine | None = None) -> None:
    """Create any missing tables. Existing tables are left untouched.

    Production must use Alembic. This helper exists so tests and a first local
    SQLite file can boot without a migration history.
    """
    settings = get_settings()
    if settings.is_production:
        raise RuntimeError(
            "create_all is not used in production. Run `alembic upgrade head`."
        )
    target = engine or get_engine()
    Base.metadata.create_all(bind=target)
    logger.info("Ensured %d table(s) exist.", len(Base.metadata.tables))


def main() -> int:  # pragma: no cover - CLI entrypoint
    configure_logging()
    create_tables()
    print(f"Created/verified tables: {', '.join(sorted(Base.metadata.tables))}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
