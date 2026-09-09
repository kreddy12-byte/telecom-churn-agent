"""Schemas shared across endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """The body of every error response."""

    code: str = Field(..., description="Stable, machine-readable error code.")
    message: str = Field(..., description="Human-readable explanation, safe to display.")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Structured context for the error, when available."
    )


class ErrorResponse(BaseModel):
    """Uniform error envelope used by every failing endpoint."""

    error: ErrorDetail

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": {
                    "code": "customer_not_found",
                    "message": "Customer '0000-XXXXX' was not found.",
                    "details": {"customer_id": "0000-XXXXX"},
                }
            }
        }
    }


class PageMeta(BaseModel):
    """Pagination metadata returned alongside list results."""

    total: int = Field(..., ge=0, description="Total records matching the query.")
    limit: int = Field(..., ge=1, description="Page size used for this response.")
    offset: int = Field(..., ge=0, description="Records skipped before this page.")
