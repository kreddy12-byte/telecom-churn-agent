"""Seed idempotency and prediction/action persistence without the HTTP layer."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import ACTION_STATUSES, STATUS_PENDING, Customer
from app.db.repositories import action_repository, customer_repository, prediction_repository
from tests.conftest import build_customer


def _dataset_record(customer_id: str, tenure: int = 5) -> dict:
    customer = build_customer(customer_id, tenure=tenure)
    return customer.to_model_record()


def test_seed_upsert_does_not_duplicate_customers(db_session) -> None:
    records = [_dataset_record("SEED-00001", tenure=1), _dataset_record("SEED-00002", tenure=2)]

    inserted, updated = customer_repository.upsert_customers(db_session, records)
    db_session.commit()
    assert inserted == 2
    assert updated == 0
    assert customer_repository.count_customers(db_session) == 2

    records[0] = _dataset_record("SEED-00001", tenure=99)
    inserted, updated = customer_repository.upsert_customers(db_session, records)
    db_session.commit()
    assert inserted == 0
    assert updated == 2
    assert customer_repository.count_customers(db_session) == 2

    refreshed = customer_repository.get_customer(db_session, "SEED-00001")
    assert refreshed is not None
    assert refreshed.tenure == 99


def test_prediction_history_is_append_only(db_session) -> None:
    db_session.add(build_customer("PRED-00001"))
    db_session.commit()

    first = prediction_repository.create_prediction(
        db_session, "PRED-00001", 0.81, "HIGH", "1.0.0"
    )
    second = prediction_repository.create_prediction(
        db_session, "PRED-00001", 0.40, "MEDIUM", "1.0.0"
    )
    db_session.commit()

    assert first.id != second.id
    assert prediction_repository.count_predictions(db_session, "PRED-00001") == 2
    latest = prediction_repository.latest_for_customer(db_session, "PRED-00001")
    assert latest is not None
    assert latest.id == second.id
    assert latest.churn_probability == 0.40


def test_action_persistence_and_status_vocabulary(db_session) -> None:
    db_session.add(build_customer("ACT-00001"))
    db_session.commit()

    action = action_repository.create_action(
        db_session,
        customer_id="ACT-00001",
        strategy_id="CONTRACT_CONVERSION",
        recommendation="Review the contract.",
    )
    db_session.commit()

    assert action.status == STATUS_PENDING
    assert STATUS_PENDING in ACTION_STATUSES
    fetched = action_repository.get_action(db_session, action.id)
    assert fetched is not None
    assert fetched.customer_id == "ACT-00001"


def test_duplicate_customer_primary_key_is_rejected(db_session) -> None:
    db_session.add(build_customer("DUP-00001"))
    db_session.commit()
    db_session.add(build_customer("DUP-00001", tenure=99))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    assert customer_repository.count_customers(db_session) == 1
    stored = customer_repository.get_customer(db_session, "DUP-00001")
    assert stored is not None
    assert stored.tenure == 12


def test_transaction_rollback_discards_partial_writes(db_session) -> None:
    db_session.add(build_customer("RB-00001"))
    db_session.flush()
    db_session.rollback()
    assert customer_repository.get_customer(db_session, "RB-00001") is None


def test_customer_round_trip_preserves_model_feature_names(db_session) -> None:
    original = build_customer("MAP-00001", contract="Month-to-month", monthly_charges=29.85)
    db_session.add(original)
    db_session.commit()

    stored = db_session.get(Customer, "MAP-00001")
    assert stored is not None
    record = stored.to_model_record()
    assert record["customerID"] == "MAP-00001"
    assert record["Contract"] == "Month-to-month"
    assert record["MonthlyCharges"] == 29.85
    assert "monthly_charges" not in record
