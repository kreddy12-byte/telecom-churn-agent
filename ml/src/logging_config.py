"""Logging setup shared by every ML entrypoint."""

from __future__ import annotations

import logging
import os
import sys

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: int | str | None = None) -> None:
    """Configure root logging for CLI runs.

    Library code should call :func:`get_logger` only; entrypoints call this.
    """
    resolved = level or os.getenv("ML_LOG_LEVEL", "INFO")
    logging.basicConfig(
        level=resolved,
        format=_LOG_FORMAT,
        datefmt=_DATE_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
