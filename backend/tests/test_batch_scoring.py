"""Batch scoring, ranking, and latest-prediction summary."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy.exc import OperationalError

from app.db.repositories import prediction_repository
from app.services.risk import classify_risk_level
from ml.src.exceptions import MLPipelineError
from tests.conftest import (
    EXPECTED_BASELINE_PROBABILITY,
    VERIFICATION_CUSTOMER_ID,
    build_customer,
    requires_trained_model,
)


def _fake_predict(
    probabilities: Mapping[str, float],
    model_version: str = "1.0.0",
):
    """Return a predict_customers stand-in that never loads artifacts."""

    def _predict(
        records: Sequence[Mapping[str, Any]],
        models_dir: object = None,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for record in records:
            customer_id = str(record["customerID"])
            probability = float(probabilities[customer_id])
            results.append(
                {
                    "churn_probability": probability,
                    "prediction": int(probability >= 0.5),
                    "risk_level": classify_risk_level(probability),
                    "model_version": model_version,
                }
            )
        return results

    return _predict


def _seed_latest_scores(db_session) -> None:
    """Three customers with known latest probabilities for ranking tests."""
    db_session.add_all(
        [
            build_customer("AAA0-AAAAA", tenure=1),
            build_customer("BBB0-BBBBB", tenure=24, contract="One year"),
            build_customer("CCC0-CCCCC", tenure=60, contract="Two year"),
        ]
    )
    db_session.commit()
    prediction_repository.create_prediction(db_session, "AAA0-AAAAA", 0.91, "HIGH", "1.0.0")
    prediction_repository.create_prediction(db_session, "BBB0-BBBBB", 0.45, "MEDIUM", "1.0.0")
    prediction_repository.create_prediction(db_session, "CCC0-CCCCC", 0.12, "LOW", "1.0.0")
    db_session.commit()


def test_classify_risk_level_uses_locked_thresholds() -> None:
    assert classify_risk_level(0.0) == "LOW"
    assert classify_risk_level(0.2999) == "LOW"
    assert classify_risk_level(0.30) == "MEDIUM"
    assert classify_risk_level(0.5999) == "MEDIUM"
    assert classify_risk_level(0.60) == "HIGH"
    assert classify_risk_level(1.0) == "HIGH"


def test_batch_scoring_empty_customer_database(client) -> None:
    response = client.post("/api/predictions/batch")
    assert response.status_code == 200
    body = response.json()
    assert body["processed"] == 0
    assert body["stored"] == 0
    assert body["risk_counts"] == {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    assert body["model_version"]
    assert body["scored_at"]


def test_batch_scoring_all_customers_with_mocked_predictor(
    client, stored_customers, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.services.batch_scoring_service.predict_customers",
        _fake_predict(
            {"AAA0-AAAAA": 0.91, "BBB0-BBBBB": 0.45, "CCC0-CCCCC": 0.12}
        ),
    )

    response = client.post("/api/predictions/batch")
    assert response.status_code == 200
    body = response.json()
    assert body["processed"] == 3
    assert body["stored"] == 3
    assert body["model_version"] == "1.0.0"
    assert body["risk_counts"] == {"HIGH": 1, "MEDIUM": 1, "LOW": 1}

    summary = client.get("/api/predictions/summary")
    assert summary.json()["total_scored"] == 3
    assert summary.json()["risk_counts"] == {"HIGH": 1, "MEDIUM": 1, "LOW": 1}


def test_batch_scoring_persists_probability_risk_and_version(
    client, stored_customers, db_session, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.services.batch_scoring_service.predict_customers",
        _fake_predict(
            {"AAA0-AAAAA": 0.91, "BBB0-BBBBB": 0.45, "CCC0-CCCCC": 0.12},
            model_version="1.0.0",
        ),
    )

    response = client.post("/api/predictions/batch")
    assert response.status_code == 200

    high = prediction_repository.latest_for_customer(db_session, "AAA0-AAAAA")
    medium = prediction_repository.latest_for_customer(db_session, "BBB0-BBBBB")
    low = prediction_repository.latest_for_customer(db_session, "CCC0-CCCCC")
    assert high is not None
    assert high.churn_probability == 0.91
    assert high.risk_level == "HIGH"
    assert high.model_version == "1.0.0"
    assert medium is not None and medium.risk_level == "MEDIUM"
    assert low is not None and low.risk_level == "LOW"


def test_repeated_batch_appends_history_without_uncontrolled_duplicates(
    client, stored_customers, db_session, monkeypatch
) -> None:
    first = _fake_predict(
        {"AAA0-AAAAA": 0.91, "BBB0-BBBBB": 0.45, "CCC0-CCCCC": 0.12}
    )
    second = _fake_predict(
        {"AAA0-AAAAA": 0.20, "BBB0-BBBBB": 0.20, "CCC0-CCCCC": 0.20}
    )
    monkeypatch.setattr(
        "app.services.batch_scoring_service.predict_customers", first
    )
    assert client.post("/api/predictions/batch").status_code == 200

    monkeypatch.setattr(
        "app.services.batch_scoring_service.predict_customers", second
    )
    repeated = client.post("/api/predictions/batch")
    assert repeated.status_code == 200
    assert repeated.json()["processed"] == 3
    assert repeated.json()["stored"] == 3
    assert repeated.json()["risk_counts"] == {"HIGH": 0, "MEDIUM": 0, "LOW": 3}

    assert prediction_repository.count_predictions(db_session, "AAA0-AAAAA") == 2
    latest = prediction_repository.latest_for_customer(db_session, "AAA0-AAAAA")
    assert latest is not None
    assert latest.churn_probability == 0.20
    assert latest.risk_level == "LOW"
    assert prediction_repository.count_predictions(db_session) == 6


def test_ranking_is_descending_by_churn_probability(client, db_session) -> None:
    _seed_latest_scores(db_session)

    response = client.get("/api/predictions/ranking")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [row["customer_id"] for row in items] == [
        "AAA0-AAAAA",
        "BBB0-BBBBB",
        "CCC0-CCCCC",
    ]
    probabilities = [row["churn_probability"] for row in items]
    assert probabilities == sorted(probabilities, reverse=True)
    assert items[0]["risk_level"] == "HIGH"
    assert items[0]["model_version"] == "1.0.0"
    assert items[0]["predicted_at"]
    assert items[0]["tenure"] == 1
    assert "top_drivers" not in items[0]
    assert "shap_value" not in items[0]
    assert "recommendation" not in items[0]


def test_ranking_filters_by_risk_band(client, db_session) -> None:
    _seed_latest_scores(db_session)

    high = client.get("/api/predictions/ranking", params={"risk": "HIGH"})
    assert high.status_code == 200
    assert [row["customer_id"] for row in high.json()["items"]] == ["AAA0-AAAAA"]
    assert high.json()["meta"]["total"] == 1

    medium = client.get("/api/predictions/ranking", params={"risk": "MEDIUM"})
    assert [row["customer_id"] for row in medium.json()["items"]] == ["BBB0-BBBBB"]

    low = client.get("/api/predictions/ranking", params={"risk": "LOW"})
    assert [row["customer_id"] for row in low.json()["items"]] == ["CCC0-CCCCC"]


def test_ranking_rejects_unknown_risk_filter(client) -> None:
    response = client.get("/api/predictions/ranking", params={"risk": "CRITICAL"})
    assert response.status_code == 422


def test_ranking_pagination(client, db_session) -> None:
    _seed_latest_scores(db_session)

    page = client.get("/api/predictions/ranking", params={"limit": 1, "offset": 1})
    assert page.status_code == 200
    body = page.json()
    assert body["meta"] == {"total": 3, "limit": 1, "offset": 1}
    assert [row["customer_id"] for row in body["items"]] == ["BBB0-BBBBB"]


def test_summary_counts_latest_predictions_only(client, db_session) -> None:
    _seed_latest_scores(db_session)

    response = client.get("/api/predictions/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_scored"] == 3
    assert body["risk_counts"] == {"HIGH": 1, "MEDIUM": 1, "LOW": 1}
    assert body["average_churn_probability"] == 0.4933
    assert body["highest_churn_probability"] == 0.91


def test_summary_and_ranking_use_latest_when_history_exists(
    client, db_session
) -> None:
    db_session.add(build_customer("HIST-00001"))
    db_session.commit()
    prediction_repository.create_prediction(
        db_session, "HIST-00001", 0.95, "HIGH", "1.0.0"
    )
    prediction_repository.create_prediction(
        db_session, "HIST-00001", 0.11, "LOW", "1.0.0"
    )
    db_session.commit()

    summary = client.get("/api/predictions/summary")
    assert summary.status_code == 200
    body = summary.json()
    assert body["total_scored"] == 1
    assert body["risk_counts"] == {"HIGH": 0, "MEDIUM": 0, "LOW": 1}
    assert body["highest_churn_probability"] == 0.11

    ranking = client.get("/api/predictions/ranking")
    assert ranking.json()["items"][0]["risk_level"] == "LOW"
    assert ranking.json()["items"][0]["churn_probability"] == 0.11
    assert prediction_repository.count_predictions(db_session, "HIST-00001") == 2


def test_summary_empty_when_nobody_is_scored(client) -> None:
    response = client.get("/api/predictions/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["total_scored"] == 0
    assert body["risk_counts"] == {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    assert body["average_churn_probability"] is None
    assert body["highest_churn_probability"] is None


def test_predictor_failure_returns_503(client, stored_customers, monkeypatch) -> None:
    def _boom(*_args: object, **_kwargs: object) -> list[dict[str, Any]]:
        raise MLPipelineError("predictor exploded")

    monkeypatch.setattr(
        "app.services.batch_scoring_service.predict_customers", _boom
    )
    response = client.post("/api/predictions/batch")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "prediction_failed"
    dumped = str(response.json()).lower()
    assert "traceback" not in dumped
    assert "exploded" not in dumped


def test_database_failure_returns_503(client, stored_customers, monkeypatch) -> None:
    def _boom(*_args: object, **_kwargs: object):
        raise OperationalError("SELECT", {}, Exception("database down"))

    monkeypatch.setattr(
        "app.services.batch_scoring_service.customer_repository.iter_customers",
        _boom,
    )
    response = client.post("/api/predictions/batch")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    dumped = str(response.json()).lower()
    assert "database down" not in dumped
    assert "traceback" not in dumped


def test_existing_single_customer_predict_contract_unchanged(client) -> None:
    """Batch routes must not change POST /api/predict's documented error shape."""
    response = client.post("/api/predict", json={"customer_id": "0000-XXXXX"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "customer_not_found"


@requires_trained_model
def test_batch_scoring_uses_real_saved_model(
    client, verification_customer, db_session
) -> None:
    extra = build_customer("REAL-00001", tenure=60, contract="Two year")
    db_session.add(extra)
    db_session.commit()

    response = client.post("/api/predictions/batch")
    assert response.status_code == 200
    body = response.json()
    assert body["processed"] == 2
    assert body["stored"] == 2
    assert body["model_version"] == "1.0.0"
    assert sum(body["risk_counts"].values()) == 2

    stored = prediction_repository.latest_for_customer(
        db_session, VERIFICATION_CUSTOMER_ID
    )
    assert stored is not None
    assert stored.churn_probability == EXPECTED_BASELINE_PROBABILITY
    assert stored.risk_level == "HIGH"
    assert stored.model_version == "1.0.0"

    ranking = client.get("/api/predictions/ranking")
    assert ranking.status_code == 200
    ids = [row["customer_id"] for row in ranking.json()["items"]]
    assert VERIFICATION_CUSTOMER_ID in ids
    assert ranking.json()["items"][0]["churn_probability"] >= ranking.json()["items"][-1][
        "churn_probability"
    ]


def test_probability_distribution_empty(client) -> None:
    response = client.get("/api/predictions/distribution")
    assert response.status_code == 200
    body = response.json()
    assert body["total_scored"] == 0
    assert [row["bucket"] for row in body["buckets"]] == [
        "0-10%",
        "10-20%",
        "20-30%",
        "30-40%",
        "40-50%",
        "50-60%",
        "60-70%",
        "70-80%",
        "80-90%",
        "90-100%",
    ]
    assert all(row["count"] == 0 for row in body["buckets"])


def test_probability_distribution_uses_latest_scores_only(client, db_session) -> None:
    db_session.add_all(
        [
            build_customer("DIST-00001"),
            build_customer("DIST-00002"),
            build_customer("DIST-00003"),
        ]
    )
    db_session.commit()
    prediction_repository.create_prediction(db_session, "DIST-00001", 0.05, "LOW", "1.0.0")
    prediction_repository.create_prediction(db_session, "DIST-00001", 0.91, "HIGH", "1.0.0")
    prediction_repository.create_prediction(db_session, "DIST-00002", 0.42, "MEDIUM", "1.0.0")
    prediction_repository.create_prediction(db_session, "DIST-00003", 0.10, "LOW", "1.0.0")
    db_session.commit()

    response = client.get("/api/predictions/distribution")
    assert response.status_code == 200
    body = response.json()
    counts = {row["bucket"]: row["count"] for row in body["buckets"]}
    assert body["total_scored"] == 3
    assert counts["90-100%"] == 1
    assert counts["40-50%"] == 1
    assert counts["10-20%"] == 1
    assert counts["0-10%"] == 0
    assert sum(counts.values()) == 3
