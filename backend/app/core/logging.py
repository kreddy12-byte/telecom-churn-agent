"""Centralized logging configuration."""

import logging
import sys

from app.core.config import get_settings


def configure_logging() -> None:
    """Configure root logger based on application settings."""
    settings = get_settings()
    level = logging.DEBUG if settings.app_debug else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger."""
    return logging.getLogger(name)
