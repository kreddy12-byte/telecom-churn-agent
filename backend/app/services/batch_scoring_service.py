"""Score every stored customer with the production predictor.

This is the second writer of prediction history (the first is
``prediction_service.predict_for_customer``). Recommendation and what-if
requests still do not persist scores.

Batch scoring calls the locked Step 2 predictor only — never SHAP, never the
LLM — so scoring ~7k rows stays a database-plus-inference job.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import PredictionFailedError
from app.core.logging import get_logger
from app.db.models.customer import Customer
from app.db.repositories import customer_repository, prediction_repository
from app.schemas.common import PageMeta
from app.schemas.prediction import (
    BatchScoringResponse,
    PredictionRankingResponse,
    PredictionSummaryResponse,
    ProbabilityBucket,
    ProbabilityDistributionResponse,
    RankedPrediction,
    RiskCounts,
)
from app.services.ml_runtime import models_dir, translate_ml_errors
from app.services.risk import classify_risk_level
from ml.src.prediction.predictor import predict_customers

logger = get_logger(__name__)

# Chunk size keeps ORM identity maps and transformed feature matrices bounded.
# 250 Telco rows is well under SQLite/PostgreSQL bind limits and small enough
# that a failed chunk does not hold thousands of pending INSERTs in memory.
BATCH_SCORE_CHUNK_SIZE = 250


# =========================================================
# 1. LOAD CUSTOMERS  /  2. RUN BATCH PREDICTION
# 3. CLASSIFY RISK   /  4. PERSIST PREDICTIONS
# 5. BUILD SUMMARY
# =========================================================


def score_all_customers(
    session: Session,
    *,
    chunk_size: int = BATCH_SCORE_CHUNK_SIZE,
) -> BatchScoringResponse:
    """Score every customer and append one history row per customer.

    History stays append-only: a second run writes a new snapshot rather than
    updating yesterday's scores. Ranking and summary always read the latest
    row per customer, so repeats do not inflate dashboard counts.

    Rows in one run share ``scored_at`` so the batch is identifiable without
    adding a ``batch_id`` column.
    """
    scored_at = datetime.now(timezone.utc)
    processed = 0
    stored = 0
    seen_ids: set[str] = set()
    risk_tally = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    model_version = get_settings().model_version

    # 1. LOAD CUSTOMERS — keyset chunks, never the full table at once.
    for chunk in customer_repository.iter_customers(session, chunk_size):
        unique_chunk = _unique_customers(chunk, seen_ids)
        if not unique_chunk:
            continue

        records = [customer.to_model_record() for customer in unique_chunk]

        # 2. RUN BATCH PREDICTION — same saved model + preprocessor as /api/predict.
        results = _predict_chunk(records)
        if len(results) != len(unique_chunk):
            raise PredictionFailedError(
                "Batch prediction failed. See the server log for details."
            )

        rows: list[tuple[str, float, str, str]] = []
        for customer, result in zip(unique_chunk, results, strict=True):
            probability = float(result["churn_probability"])
            # 3. CLASSIFY RISK — use the predictor's band when present (it already
            # applies the locked thresholds on the unrounded probability). Fall
            # back to the shared helper so a mock or older artifact cannot skip
            # banding.
            risk_level = str(result.get("risk_level") or classify_risk_level(probability))
            version = str(result["model_version"])
            model_version = version
            risk_tally[risk_level] = risk_tally.get(risk_level, 0) + 1
            rows.append((customer.customer_id, probability, risk_level, version))

        # 4. PERSIST PREDICTIONS — one flush per chunk; one commit for the run.
        stored += prediction_repository.create_predictions(
            session, rows, created_at=scored_at
        )
        processed += len(unique_chunk)

    session.commit()

    logger.info(
        "Batch scored %s customers (%s rows stored, model %s)",
        processed,
        stored,
        model_version,
    )

    # 5. BUILD SUMMARY — this run's tally, not a recount of historical rows.
    return BatchScoringResponse(
        processed=processed,
        stored=stored,
        model_version=model_version,
        scored_at=scored_at,
        risk_counts=RiskCounts(
            HIGH=risk_tally.get("HIGH", 0),
            MEDIUM=risk_tally.get("MEDIUM", 0),
            LOW=risk_tally.get("LOW", 0),
        ),
    )


def rank_latest_predictions(
    session: Session,
    *,
    risk: str | None,
    limit: int,
    offset: int,
) -> PredictionRankingResponse:
    """Latest stored score per customer, highest churn probability first."""
    pairs = prediction_repository.list_latest_ranked(
        session, risk_level=risk, limit=limit, offset=offset
    )
    total = prediction_repository.count_latest_ranked(session, risk_level=risk)
    items = [
        RankedPrediction(
            customer_id=customer.customer_id,
            tenure=customer.tenure,
            contract=customer.contract,
            monthly_charges=customer.monthly_charges,
            internet_service=customer.internet_service,
            churn_probability=prediction.churn_probability,
            risk_level=prediction.risk_level,  # type: ignore[arg-type]
            model_version=prediction.model_version,
            predicted_at=prediction.created_at,
        )
        for customer, prediction in pairs
    ]
    return PredictionRankingResponse(
        items=items,
        meta=PageMeta(total=total, limit=limit, offset=offset),
    )


def summarize_latest_predictions(session: Session) -> PredictionSummaryResponse:
    """HIGH / MEDIUM / LOW and probability stats from the latest row per customer."""
    stats = prediction_repository.latest_prediction_stats(session)
    counts = stats["risk_counts"]
    return PredictionSummaryResponse(
        total_scored=stats["total_scored"],
        risk_counts=RiskCounts(
            HIGH=int(counts.get("HIGH", 0)),
            MEDIUM=int(counts.get("MEDIUM", 0)),
            LOW=int(counts.get("LOW", 0)),
        ),
        average_churn_probability=stats["average_churn_probability"],
        highest_churn_probability=stats["highest_churn_probability"],
    )


def probability_distribution(session: Session) -> ProbabilityDistributionResponse:
    """Histogram of latest churn probabilities in 10-point bands."""
    rows = prediction_repository.latest_probability_distribution(session)
    total = sum(count for _label, count in rows)
    return ProbabilityDistributionResponse(
        buckets=[ProbabilityBucket(bucket=label, count=count) for label, count in rows],
        total_scored=total,
    )


# =========================================================
# HELPERS
# =========================================================


def _predict_chunk(records: list[dict]) -> list[dict]:
    """Score one chunk through the cached production predictor."""
    with translate_ml_errors("Batch prediction", PredictionFailedError):
        return predict_customers(records, models_dir=models_dir())


def _unique_customers(
    chunk: list[Customer], seen_ids: set[str]
) -> list[Customer]:
    """Drop a customer already scored in this run so one batch cannot double-insert."""
    unique: list[Customer] = []
    for customer in chunk:
        if customer.customer_id in seen_ids:
            continue
        seen_ids.add(customer.customer_id)
        unique.append(customer)
    return unique
