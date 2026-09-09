"""Application error types and their HTTP mapping.

One place decides which failures are the client's fault, which are ours, and
what the caller is told. Error *messages* are written for an API consumer:
they never contain a stack trace, a connection string, an API key, a provider
URL, or a request header.
"""

from __future__ import annotations

from typing import Any

from fastapi import status


# =========================================================
# 1. BASE ERROR
# =========================================================


class AppError(Exception):
    """An error with a known cause, safe to report to the caller.

    Anything not derived from this is treated as an internal fault and reported
    as a generic 500 with the detail confined to the server log.
    """

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_code: str = "internal_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


# =========================================================
# 2. CLIENT ERRORS
# =========================================================


class CustomerNotFoundError(AppError):
    """The requested customer is not in the database."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "customer_not_found"

    def __init__(self, customer_id: str) -> None:
        super().__init__(
            f"Customer '{customer_id}' was not found. "
            "Seed the database with `python -m app.db.seed` if it should exist.",
            {"customer_id": customer_id},
        )


class ActionNotFoundError(AppError):
    """The requested action record does not exist."""

    status_code = status.HTTP_404_NOT_FOUND
    error_code = "action_not_found"

    def __init__(self, action_id: int) -> None:
        super().__init__(f"Action {action_id} was not found.", {"action_id": action_id})


class InvalidCustomerDataError(AppError):
    """The stored customer record cannot be scored by the model.

    422 rather than 500: the data is at fault, not the service, and the caller
    can act on it by correcting the record.
    """

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "invalid_customer_data"


class InvalidScenarioError(AppError):
    """A what-if scenario was rejected by the simulator's validation."""

    status_code = status.HTTP_400_BAD_REQUEST
    error_code = "invalid_scenario"


class InvalidActionTransitionError(AppError):
    """The requested review transition is not permitted by the workflow."""

    status_code = status.HTTP_409_CONFLICT
    error_code = "invalid_action_transition"

    def __init__(self, current_status: str, requested_status: str, allowed: list[str]) -> None:
        allowed_text = ", ".join(allowed) if allowed else "no further transitions"
        super().__init__(
            f"An action in status {current_status} cannot move to {requested_status}. "
            f"Allowed from {current_status}: {allowed_text}.",
            {
                "current_status": current_status,
                "requested_status": requested_status,
                "allowed_statuses": allowed,
            },
        )


class ReviewerNoteRequiredError(AppError):
    """A reviewer note is mandatory for this decision."""

    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    error_code = "reviewer_note_required"

    def __init__(self, requested_status: str) -> None:
        super().__init__(
            f"A reviewer note is required when setting an action to {requested_status}, "
            "so the decision is auditable.",
            {"requested_status": requested_status},
        )


# =========================================================
# 3. SERVICE-SIDE ERRORS
# =========================================================


class ModelUnavailableError(AppError):
    """Trained model artifacts are missing or unreadable.

    503 rather than 500: the service is correctly deployed but a dependency it
    needs is absent, and the fix is operational.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "model_unavailable"


class ExplanationFailedError(AppError):
    """The SHAP explanation could not be produced."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "explanation_failed"


class PredictionFailedError(AppError):
    """Batch (or predictor-only) scoring could not be completed."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "prediction_failed"


class RecommendationFailedError(AppError):
    """The retention recommendation could not be produced.

    Note that an unavailable LLM is *not* this error: the agent degrades to its
    deterministic engine and still returns a recommendation.
    """

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "recommendation_failed"


class SimulationFailedError(AppError):
    """The what-if simulation could not be completed."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "simulation_failed"


class ConflictError(AppError):
    """The write conflicts with an existing row (duplicate key, etc.)."""

    status_code = status.HTTP_409_CONFLICT
    error_code = "conflict"

    def __init__(self) -> None:
        super().__init__("The request conflicts with data that already exists.")


class DatabaseUnavailableError(AppError):
    """The database could not be reached or a query failed."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    error_code = "database_unavailable"

    def __init__(self) -> None:
        # No driver text: it can carry the host, port, and user from the DSN.
        super().__init__("The database is currently unavailable. Please try again later.")


class UnauthenticatedError(AppError):
    """The request has no valid access token.

    The message is intentionally generic: callers learn that they must
    authenticate, not why a particular token failed (expired, wrong
    issuer, bad signature, …).
    """

    status_code = status.HTTP_401_UNAUTHORIZED
    error_code = "unauthenticated"

    def __init__(self) -> None:
        super().__init__("Authentication required.")


class ForbiddenError(AppError):
    """The caller is authenticated but not allowed to use this resource."""

    status_code = status.HTTP_403_FORBIDDEN
    error_code = "forbidden"

    def __init__(self) -> None:
        super().__init__("You do not have permission to access this resource.")
