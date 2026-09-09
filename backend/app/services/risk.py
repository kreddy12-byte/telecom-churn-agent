"""Shared churn-risk banding for the backend.

Thresholds are owned by the locked ML config (0.30 / 0.60). This module is the
backend's single import site so services never copy those literals and never
drift from the predictor that produced the score.
"""

from __future__ import annotations

from ml.src.config import risk_level_for


def classify_risk_level(probability: float) -> str:
    """Map a churn probability onto LOW / MEDIUM / HIGH.

    Delegates to ``ml.src.config.risk_level_for`` so batch scoring, ranking
    filters, and tests share the same contract as ``POST /api/predict``.
    """
    return risk_level_for(probability)
