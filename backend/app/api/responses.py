"""OpenAPI response declarations shared by the route modules.

Documenting the failure modes is part of the contract: a client should be able
to read the schema and know that a prediction can return 404, 422, or 503
without discovering it in production.
"""

from __future__ import annotations

from typing import Any

from app.schemas.common import ErrorResponse

_ERROR = {"model": ErrorResponse}

CUSTOMER_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {**_ERROR, "description": "No customer with that identifier."},
}

ACTION_NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {**_ERROR, "description": "No action with that identifier."},
}

MODEL_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {**_ERROR, "description": "No customer with that identifier."},
    422: {**_ERROR, "description": "The stored customer record cannot be scored."},
    503: {**_ERROR, "description": "Trained model artifacts are unavailable."},
}

BATCH_ERRORS: dict[int | str, dict[str, Any]] = {
    422: {**_ERROR, "description": "A stored customer record cannot be scored."},
    503: {**_ERROR, "description": "The model or the database is unavailable."},
}

SIMULATION_ERRORS: dict[int | str, dict[str, Any]] = {
    400: {**_ERROR, "description": "A requested scenario is unknown or invalid."},
    **MODEL_ERRORS,
}

REVIEW_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {**_ERROR, "description": "Missing or invalid access token."},
    404: {**_ERROR, "description": "No action with that identifier."},
    409: {**_ERROR, "description": "The review workflow does not permit this transition."},
    422: {**_ERROR, "description": "A reviewer note is required for this decision."},
}

AUTH_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {**_ERROR, "description": "Missing or invalid access token."},
}
