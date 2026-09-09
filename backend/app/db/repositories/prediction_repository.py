"""Data access for prediction history (append-only)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.db.models.customer import Customer
from app.db.models.prediction import Prediction


# =========================================================
# 1. WRITES
# =========================================================


def create_prediction(
    session: Session,
    customer_id: str,
    churn_probability: float,
    risk_level: str,
    model_version: str,
    created_at: datetime | None = None,
) -> Prediction:
    """Append a prediction to the customer's history.

    There is no update counterpart on purpose — history is never rewritten.
    ``created_at`` is optional so a batch run can stamp every row with the
    same clock time and stay identifiable without a ``batch_id`` column.
    """
    fields: dict[str, Any] = {
        "customer_id": customer_id,
        "churn_probability": churn_probability,
        "risk_level": risk_level,
        "model_version": model_version,
    }
    if created_at is not None:
        fields["created_at"] = created_at
    prediction = Prediction(**fields)
    session.add(prediction)
    session.flush()
    return prediction


def create_predictions(
    session: Session,
    rows: Sequence[tuple[str, float, str, str]],
    created_at: datetime | None = None,
) -> int:
    """Append many history rows in one flush.

    Used by batch scoring so a chunk of customers becomes one database
    round-trip rather than one INSERT per customer. Still insert-only.
    """
    for customer_id, churn_probability, risk_level, model_version in rows:
        fields: dict[str, Any] = {
            "customer_id": customer_id,
            "churn_probability": churn_probability,
            "risk_level": risk_level,
            "model_version": model_version,
        }
        if created_at is not None:
            fields["created_at"] = created_at
        session.add(Prediction(**fields))
    session.flush()
    return len(rows)


# =========================================================
# 2. READS
# =========================================================


def latest_for_customer(session: Session, customer_id: str) -> Prediction | None:
    """Most recent prediction for one customer, or None if never scored."""
    statement = (
        select(Prediction)
        .where(Prediction.customer_id == customer_id)
        .order_by(Prediction.id.desc())
        .limit(1)
    )
    return session.scalars(statement).first()


def latest_for_customers(
    session: Session, customer_ids: Sequence[str]
) -> dict[str, Prediction]:
    """Most recent prediction per customer, keyed by identifier.

    Two queries rather than one per customer, so listing a page of customers
    never degrades into N+1 lookups. Recency is resolved by primary key because
    the table is append-only, which makes the highest id the newest row and
    avoids ties between predictions written in the same clock tick.
    """
    ids = list(customer_ids)
    if not ids:
        return {}

    newest_ids = session.scalars(
        select(func.max(Prediction.id))
        .where(Prediction.customer_id.in_(ids))
        .group_by(Prediction.customer_id)
    ).all()
    if not newest_ids:
        return {}

    rows = session.scalars(select(Prediction).where(Prediction.id.in_(newest_ids)))
    return {prediction.customer_id: prediction for prediction in rows}


def count_predictions(session: Session, customer_id: str | None = None) -> int:
    """Number of stored predictions, optionally for a single customer."""
    statement = select(func.count()).select_from(Prediction)
    if customer_id is not None:
        statement = statement.where(Prediction.customer_id == customer_id)
    return int(session.scalar(statement) or 0)


def count_evaluated_customers(session: Session) -> int:
    """Distinct customers that have at least one stored prediction."""
    return int(
        session.scalar(select(func.count(func.distinct(Prediction.customer_id)))) or 0
    )


def latest_risk_counts(session: Session) -> dict[str, int]:
    """Risk-band counts using each customer's most recent prediction only."""
    newest_ids = select(func.max(Prediction.id)).group_by(Prediction.customer_id)
    rows = session.execute(
        select(Prediction.risk_level, func.count())
        .where(Prediction.id.in_(newest_ids))
        .group_by(Prediction.risk_level)
    )
    return {level: int(count) for level, count in rows}


def recent_high_risk(session: Session, limit: int = 8) -> list[Prediction]:
    """Latest HIGH-risk predictions, newest first."""
    newest_ids = select(func.max(Prediction.id)).group_by(Prediction.customer_id)
    statement = (
        select(Prediction)
        .where(Prediction.id.in_(newest_ids), Prediction.risk_level == "HIGH")
        .order_by(Prediction.id.desc())
        .limit(limit)
    )
    return list(session.scalars(statement))


def _latest_prediction_ids():
    """Subquery: the append-only max(id) per customer is that customer's latest score."""
    return select(func.max(Prediction.id)).group_by(Prediction.customer_id)


def list_latest_ranked(
    session: Session,
    *,
    risk_level: str | None,
    limit: int,
    offset: int,
) -> list[tuple[Customer, Prediction]]:
    """Latest score per customer, highest churn probability first.

    Recency is the highest prediction id, not created_at, because a batch run
    stamps every row with the same timestamp and a clock-based "latest" would
    then be ambiguous.
    """
    statement = (
        select(Customer, Prediction)
        .join(Prediction, Prediction.customer_id == Customer.customer_id)
        .where(Prediction.id.in_(_latest_prediction_ids()))
    )
    if risk_level:
        statement = statement.where(Prediction.risk_level == risk_level)
    statement = (
        statement.order_by(Prediction.churn_probability.desc(), Prediction.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(session.execute(statement).all())


def count_latest_ranked(session: Session, risk_level: str | None = None) -> int:
    """How many customers have a latest score, optionally in one risk band."""
    statement = (
        select(func.count())
        .select_from(Prediction)
        .where(Prediction.id.in_(_latest_prediction_ids()))
    )
    if risk_level:
        statement = statement.where(Prediction.risk_level == risk_level)
    return int(session.scalar(statement) or 0)


def latest_prediction_stats(session: Session) -> dict[str, Any]:
    """Latest-per-customer totals: counts, average probability, highest probability.

    Historical rows are excluded by restricting to max(id) per customer, so a
    second batch run cannot inflate HIGH/MEDIUM/LOW totals.
    """
    latest = _latest_prediction_ids()
    total, average, highest = session.execute(
        select(
            func.count(),
            func.avg(Prediction.churn_probability),
            func.max(Prediction.churn_probability),
        ).where(Prediction.id.in_(latest))
    ).one()

    risk_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    risk_counts.update(latest_risk_counts(session))

    return {
        "total_scored": int(total or 0),
        "risk_counts": risk_counts,
        "average_churn_probability": (
            round(float(average), 4) if average is not None else None
        ),
        "highest_churn_probability": (
            float(highest) if highest is not None else None
        ),
    }


# Ten equal-width probability bands. The last band is closed on the right so a
# score of exactly 1.0 is counted instead of dropped.
PROBABILITY_BUCKETS: tuple[tuple[str, float], ...] = (
    ("0-10%", 0.10),
    ("10-20%", 0.20),
    ("20-30%", 0.30),
    ("30-40%", 0.40),
    ("40-50%", 0.50),
    ("50-60%", 0.60),
    ("60-70%", 0.70),
    ("70-80%", 0.80),
    ("80-90%", 0.90),
    ("90-100%", 1.01),
)


def latest_probability_distribution(session: Session) -> list[tuple[str, int]]:
    """Count latest scores per 10-point probability band.

    Aggregation happens in SQL so the dashboard never ships 7k rows to count
    them in the browser. Latest-per-customer uses max(id), matching summary.
    """
    whens = [
        (Prediction.churn_probability < upper, label)
        for label, upper in PROBABILITY_BUCKETS[:-1]
    ]
    bucket_expr = case(*whens, else_=PROBABILITY_BUCKETS[-1][0])
    rows = session.execute(
        select(bucket_expr, func.count())
        .where(Prediction.id.in_(_latest_prediction_ids()))
        .group_by(bucket_expr)
    )
    counted = {str(label): int(count) for label, count in rows}
    return [(label, counted.get(label, 0)) for label, _upper in PROBABILITY_BUCKETS]
