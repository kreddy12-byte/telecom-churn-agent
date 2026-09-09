"""Load the Telco customer dataset into PostgreSQL.

The CSV itself is never stored. Each row is parsed into a typed customer record;
the file stays on disk as the ML pipeline's input.

Seeding is idempotent because the dataset's own ``customerID`` is the primary
key: a second run updates the existing rows rather than inserting duplicates.

Usage::

    python -m app.db.seed
    python -m app.db.seed --limit 100      # smaller local dataset
"""

from __future__ import annotations

import argparse
from typing import Any

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.init_db import create_tables
from app.db.repositories import customer_repository
from app.db.session import get_session_factory
from ml.src import config as ml_config
from ml.src.data.clean_dataset import coerce_numeric_columns, strip_whitespace
from ml.src.data.validate_dataset import load_raw_dataset

logger = get_logger(__name__)


# =========================================================
# 1. READ AND PREPARE DATASET ROWS
# =========================================================


def load_customer_records(limit: int | None = None) -> list[dict[str, Any]]:
    """Read the raw dataset and return one plain-Python record per customer.

    Reuses the ML layer's own cleaning helpers so stored values match what the
    model sees at inference. The churn label is not read: it is training ground
    truth, not a customer attribute, and storing it would invite using it as a
    feature.
    """
    frame = load_raw_dataset()

    # Blank strings become NaN and the charge columns become real numbers —
    # the same two steps the training pipeline applies.
    frame = strip_whitespace(frame)
    frame, _ = coerce_numeric_columns(frame)

    keep = [ml_config.ID_COLUMN, *ml_config.FEATURE_COLUMNS]
    frame = frame[keep]

    if limit is not None:
        frame = frame.head(limit)

    # NaN is not a value PostgreSQL understands; NULL is.
    frame = frame.astype(object).where(pd.notna(frame), None)
    return frame.to_dict(orient="records")


# =========================================================
# 2. SEED
# =========================================================


def seed_customers(session: Session, limit: int | None = None) -> tuple[int, int]:
    """Insert or refresh customers from the dataset.

    Returns:
        ``(inserted_count, updated_count)``.
    """
    records = load_customer_records(limit=limit)
    inserted, updated = customer_repository.upsert_customers(session, records)
    session.commit()

    logger.info("Seed complete: %d inserted, %d updated.", inserted, updated)
    return inserted, updated


def main() -> int:  # pragma: no cover - CLI entrypoint
    configure_logging()
    parser = argparse.ArgumentParser(description="Seed customers from the Telco dataset.")
    parser.add_argument("--limit", type=int, default=None, help="Seed only the first N rows.")
    args = parser.parse_args()

    settings = get_settings()
    if settings.is_production:
        logger.info("Production seed assumes Alembic has already created the schema.")
    else:
        create_tables()

    with get_session_factory()() as session:
        inserted, updated = seed_customers(session, limit=args.limit)

    print(f"Customers inserted: {inserted}")
    print(f"Customers updated : {updated}")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
