"""Domain-specific exceptions for the ML pipeline.

Narrow exception types let callers (including the FastAPI backend) distinguish
recoverable user errors from genuine pipeline failures.
"""

from __future__ import annotations


class MLPipelineError(Exception):
    """Base class for all ML pipeline errors."""


class DatasetDownloadError(MLPipelineError):
    """Raised when the dataset cannot be retrieved from any known source."""


class DatasetNotFoundError(MLPipelineError):
    """Raised when the raw dataset file is missing on disk."""


class DatasetValidationError(MLPipelineError):
    """Raised when the dataset fails a blocking validation rule."""


class ModelArtifactNotFoundError(MLPipelineError):
    """Raised when a trained artifact is required but not present on disk."""


class InvalidPredictionInputError(MLPipelineError):
    """Raised when prediction input is malformed or missing required features."""
