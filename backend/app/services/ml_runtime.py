"""The seam between the backend and the locked ML/agent layers.

Two things live here so they are defined once rather than in five services:

1. Where the model artifacts are (a settings override, or the ML package default).
2. How the intelligence layers' exceptions map onto API errors.

No prediction, explanation, or simulation logic — those belong to ``ml/`` and
``agent/``, which this phase does not modify.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import AppError, InvalidCustomerDataError, ModelUnavailableError
from app.core.logging import get_logger
from ml.src.exceptions import (
    InvalidPredictionInputError,
    MLPipelineError,
    ModelArtifactNotFoundError,
)

logger = get_logger(__name__)


# =========================================================
# 1. ARTIFACT LOCATION
# =========================================================


def models_dir() -> Path | None:
    """Artifact directory for this deployment, or None for the ML default."""
    configured = get_settings().models_dir_or_none
    return Path(configured) if configured else None


# =========================================================
# 2. ERROR TRANSLATION
# =========================================================


@contextmanager
def translate_ml_errors(operation: str, failure: type[AppError]) -> Iterator[None]:
    """Convert ML-layer exceptions into API errors with safe messages.

    Args:
        operation: What was being attempted, used in the message and the log.
        failure: The error class to raise for a generic pipeline failure —
            each caller supplies the one that fits its endpoint.

    Missing artifacts and bad input are always mapped the same way regardless of
    caller: an absent model is an operational problem (503) and an unscoreable
    record is a data problem (422).
    """
    try:
        yield
    except ModelArtifactNotFoundError as exc:
        logger.error("%s failed — model artifacts unavailable: %s", operation, exc)
        raise ModelUnavailableError(
            "The trained model artifacts are not available on this server. "
            "Train the model with `python -m ml.src.training.train`."
        ) from exc
    except InvalidPredictionInputError as exc:
        # The message names the offending feature and never contains internals.
        logger.warning("%s rejected the customer record: %s", operation, exc)
        raise InvalidCustomerDataError(f"The customer record cannot be scored: {exc}") from exc
    except MLPipelineError as exc:
        logger.exception("%s failed inside the ML pipeline.", operation)
        raise failure(f"{operation} failed. See the server log for details.") from exc
