"""Data access for customers.

Repositories own SQL and nothing else: no ML calls, no HTTP concerns, no
transaction management. Services decide when to commit.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.customer import ID_DATASET_COLUMN, Customer
from app.db.models.prediction import Prediction


# =========================================================
# 1. READS
# =========================================================


def get_customer(session: Session, customer_id: str) -> Customer | None:
    """Fetch one customer by identifier, or None when absent."""
    return session.get(Customer, customer_id)


def _filtered_customer_query(query: str | None, risk_level: str | None):
    """Build the shared filter used by list and count so pagination stays honest."""
    statement = select(Customer)
    if query:
        needle = query.strip().lower()
        statement = statement.where(func.lower(Customer.customer_id).like(f"%{needle}%"))
    if risk_level:
        newest_ids = (
            select(func.max(Prediction.id))
            .group_by(Prediction.customer_id)
            .scalar_subquery()
        )
        statement = statement.join(
            Prediction,
            (Prediction.customer_id == Customer.customer_id)
            & (Prediction.id.in_(newest_ids)),
        ).where(Prediction.risk_level == risk_level)
    return statement


def list_customers(
    session: Session,
    limit: int,
    offset: int,
    query: str | None = None,
    risk_level: str | None = None,
) -> list[Customer]:
    """Fetch a page of customers ordered by identifier.

    Optional ``query`` matches a substring of ``customer_id``. Optional
    ``risk_level`` keeps only customers whose *latest stored* prediction is in
    that band — it never runs the model.
    """
    statement = (
        _filtered_customer_query(query, risk_level)
        .order_by(Customer.customer_id)
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(statement))


def count_customers(
    session: Session, query: str | None = None, risk_level: str | None = None
) -> int:
    """Total customers matching the same filters as :func:`list_customers`."""
    statement = _filtered_customer_query(query, risk_level)
    return int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)


def iter_customers(session: Session, chunk_size: int) -> Iterator[list[Customer]]:
    """Yield the full customer table in primary-key chunks.

    Keyset pagination (``customer_id > last``) is used instead of OFFSET so a
    scoring run never materialises 7k+ ORM objects at once and never skips or
    repeats a row if the table is written to during the run.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be at least 1")

    last_id: str | None = None
    while True:
        statement = select(Customer).order_by(Customer.customer_id).limit(chunk_size)
        if last_id is not None:
            statement = statement.where(Customer.customer_id > last_id)
        chunk = list(session.scalars(statement))
        if not chunk:
            break
        yield chunk
        last_id = chunk[-1].customer_id


# SQLite's default bound-variable limit is 999; PostgreSQL is far higher.
# Seeding the full Telco dataset (~7,043 ids) must not trip either.
_IN_CLAUSE_BATCH_SIZE = 500


def existing_customer_ids(session: Session, customer_ids: Iterable[str]) -> set[str]:
    """Return which of the given identifiers are already stored."""
    ids = list(customer_ids)
    if not ids:
        return set()

    found: set[str] = set()
    for start in range(0, len(ids), _IN_CLAUSE_BATCH_SIZE):
        chunk = ids[start : start + _IN_CLAUSE_BATCH_SIZE]
        statement = select(Customer.customer_id).where(Customer.customer_id.in_(chunk))
        found.update(session.scalars(statement))
    return found


# =========================================================
# 2. WRITES
# =========================================================


def upsert_customers(session: Session, records: Iterable[Mapping[str, Any]]) -> tuple[int, int]:
    """Insert new customers and refresh existing ones from dataset records.

    Matching on the dataset's own identifier is what makes seeding idempotent:
    re-running it updates rows in place instead of creating duplicates.

    Returns:
        ``(inserted_count, updated_count)``.
    """
    records = list(records)
    incoming_ids = [str(record[ID_DATASET_COLUMN]).strip() for record in records]
    already_stored = existing_customer_ids(session, incoming_ids)

    inserted = 0
    updated = 0

    for customer_id, record in zip(incoming_ids, records, strict=True):
        if customer_id in already_stored:
            customer = session.get(Customer, customer_id)
            if customer is None:  # pragma: no cover - defensive, id came from the DB
                continue
            for attribute, value in Customer.field_values_from_dataset_record(record).items():
                setattr(customer, attribute, value)
            updated += 1
        else:
            session.add(Customer.from_dataset_record(record))
            already_stored.add(customer_id)  # guards duplicates inside one batch
            inserted += 1

    session.flush()
    return inserted, updated
