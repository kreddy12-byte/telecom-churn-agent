"""HTTP exception handlers.

One module decides how every failure looks on the wire. Handlers never include
stack traces, connection strings, API keys, provider URLs, or request headers.
Those stay in the server log.
"""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError

from app.core.errors import AppError, ConflictError, DatabaseUnavailableError
from app.core.logging import get_logger

logger = get_logger(__name__)


# =========================================================
# 1. RESPONSE SHAPE
# =========================================================


def _error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


# =========================================================
# 2. HANDLERS
# =========================================================


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the application's error handlers to a FastAPI instance."""

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        # AppError messages are written for the caller; log at warning unless
        # this is an operational failure the operator needs to see.
        if exc.status_code >= 500:
            logger.error("AppError %s: %s", exc.error_code, exc.message)
        else:
            logger.warning("AppError %s: %s", exc.error_code, exc.message)
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.error_code, exc.message, exc.details),
            headers=headers or {},
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # FastAPI's default 422 body includes the submitted values. We keep the
        # field locations and messages and drop the input, so a mistyped key
        # cannot echo a secret back at the caller.
        safe_errors = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body(
                "validation_error",
                "The request did not match the expected schema.",
                {"errors": safe_errors},
            ),
        )

    @app.exception_handler(OperationalError)
    async def handle_operational_error(_request: Request, exc: OperationalError) -> JSONResponse:
        # Driver text often contains the DSN. Log the type only; never the args.
        logger.error("Database operational error (%s).", type(exc).__name__)
        wrapped = DatabaseUnavailableError()
        return JSONResponse(
            status_code=wrapped.status_code,
            content=_error_body(wrapped.error_code, wrapped.message),
        )

    @app.exception_handler(IntegrityError)
    async def handle_integrity_error(_request: Request, exc: IntegrityError) -> JSONResponse:
        logger.warning("Database integrity error (%s).", type(exc).__name__)
        wrapped = ConflictError()
        return JSONResponse(
            status_code=wrapped.status_code,
            content=_error_body(wrapped.error_code, wrapped.message),
        )

    @app.exception_handler(SQLAlchemyError)
    async def handle_sqlalchemy_error(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("Unhandled database error: %s", type(exc).__name__)
        wrapped = DatabaseUnavailableError()
        return JSONResponse(
            status_code=wrapped.status_code,
            content=_error_body(wrapped.error_code, wrapped.message),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error: %s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(
                "internal_error",
                "An unexpected error occurred. Please try again later.",
            ),
        )
