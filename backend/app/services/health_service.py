"""Health and readiness checks.

``GET /health`` stays a process-liveness probe: it never opens a database
connection and never includes credentials. ``GET /readiness`` is the deploy
probe that confirms PostgreSQL (or the configured development database) answers.
"""

from app.core.errors import DatabaseUnavailableError
from app.core.logging import get_logger
from app.db.session import check_database_connectivity
from app.schemas.health import HealthResponse, ReadinessResponse

logger = get_logger(__name__)


class HealthService:
    """Provides application health status."""

    @staticmethod
    def check() -> HealthResponse:
        """Return a healthy status payload without touching the database."""
        return HealthResponse(status="healthy")

    @staticmethod
    def readiness() -> ReadinessResponse:
        """Confirm the configured database accepts a trivial query."""
        try:
            check_database_connectivity()
        except Exception:
            # Driver messages include hosts and passwords. Do not log them.
            logger.error("Readiness check failed: database unreachable.")
            raise DatabaseUnavailableError() from None
        return ReadinessResponse(status="ready")
