"""Health and readiness routes."""

from fastapi import APIRouter

from app.schemas.health import HealthResponse, ReadinessResponse
from app.services.health_service import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Process liveness. Does not query the database."""
    return HealthService.check()


@router.get("/readiness", response_model=ReadinessResponse)
def readiness_check() -> ReadinessResponse:
    """Deploy probe: the process and the configured database are reachable."""
    return HealthService.readiness()
