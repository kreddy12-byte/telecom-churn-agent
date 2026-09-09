"""Health and readiness response schemas."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response body for GET /health (process liveness)."""

    status: str = Field(..., examples=["healthy"])


class ReadinessResponse(BaseModel):
    """Response body for GET /readiness (process + database)."""

    status: str = Field(..., examples=["ready"])
