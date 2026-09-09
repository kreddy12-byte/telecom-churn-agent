"""Tests for the reusable prediction interface."""

from __future__ import annotations

import json

import pytest

from ml.src import config
from ml.src.exceptions import (
    InvalidPredictionInputError,
    MLPipelineError,
    ModelArtifactNotFoundError,
)
from ml.src.prediction.predictor import ChurnPredictor, predict_customer, predict_customers

EXPECTED_KEYS = {"churn_probability", "prediction", "risk_level", "model_version"}


class TestRiskLevelMapping:
    @pytest.mark.parametrize(
        ("probability", "expected"),
        [
            (0.0, config.RISK_LEVEL_LOW),
            (0.2999, config.RISK_LEVEL_LOW),
            (0.30, config.RISK_LEVEL_MEDIUM),
            (0.5999, config.RISK_LEVEL_MEDIUM),
            (0.60, config.RISK_LEVEL_HIGH),
            (1.0, config.RISK_LEVEL_HIGH),
        ],
    )
    def test_thresholds(self, probability, expected):
        assert config.risk_level_for(probability) == expected


class TestPredictionOutput:
    def test_returns_contract_shape(self, trained_models_dir, sample_customer):
        result = ChurnPredictor(trained_models_dir).predict(sample_customer)
        assert set(result) == EXPECTED_KEYS

    def test_probability_within_bounds(self, trained_models_dir, sample_customer):
        result = ChurnPredictor(trained_models_dir).predict(sample_customer)
        assert 0.0 <= result["churn_probability"] <= 1.0

    def test_prediction_is_binary(self, trained_models_dir, sample_customer):
        result = ChurnPredictor(trained_models_dir).predict(sample_customer)
        assert result["prediction"] in (0, 1)

    def test_prediction_matches_probability_threshold(self, trained_models_dir, sample_customer):
        result = ChurnPredictor(trained_models_dir).predict(sample_customer)
        assert result["prediction"] == int(result["churn_probability"] >= 0.5)

    def test_risk_level_matches_probability(self, trained_models_dir, sample_customer):
        result = ChurnPredictor(trained_models_dir).predict(sample_customer)
        assert result["risk_level"] == config.risk_level_for(result["churn_probability"])

    def test_model_version_from_metadata(self, trained_models_dir, sample_customer):
        result = ChurnPredictor(trained_models_dir).predict(sample_customer)
        assert result["model_version"] == config.MODEL_VERSION

    def test_predictions_are_deterministic(self, trained_models_dir, sample_customer):
        predictor = ChurnPredictor(trained_models_dir)
        assert predictor.predict(sample_customer) == predictor.predict(sample_customer)

    def test_different_customers_can_differ(self, trained_models_dir, raw_frame):
        predictor = ChurnPredictor(trained_models_dir)
        records = raw_frame.drop(columns=[config.TARGET_COLUMN]).head(25).to_dict("records")
        probabilities = {predictor.predict(record)["churn_probability"] for record in records}
        assert len(probabilities) > 1, "Model output is constant — predictions look hardcoded."

    def test_module_level_helper(self, trained_models_dir, sample_customer):
        result = predict_customer(sample_customer, models_dir=trained_models_dir)
        assert set(result) == EXPECTED_KEYS


class TestBatchPrediction:
    def test_batch_length_matches_input(self, trained_models_dir, raw_frame):
        records = raw_frame.drop(columns=[config.TARGET_COLUMN]).head(5).to_dict("records")
        results = predict_customers(records, models_dir=trained_models_dir)
        assert len(results) == 5
        assert all(set(result) == EXPECTED_KEYS for result in results)

    def test_batch_matches_single_prediction(self, trained_models_dir, raw_frame):
        records = raw_frame.drop(columns=[config.TARGET_COLUMN]).head(3).to_dict("records")
        predictor = ChurnPredictor(trained_models_dir)
        batch = predictor.predict_batch(records)
        singles = [predictor.predict(record) for record in records]
        assert batch == singles


class TestInputValidation:
    def test_missing_feature_raises(self, trained_models_dir, sample_customer):
        incomplete = dict(sample_customer)
        incomplete.pop("Contract")
        with pytest.raises(InvalidPredictionInputError, match="Contract"):
            ChurnPredictor(trained_models_dir).predict(incomplete)

    def test_empty_mapping_raises(self, trained_models_dir):
        with pytest.raises(InvalidPredictionInputError):
            ChurnPredictor(trained_models_dir).predict({})

    def test_non_mapping_raises(self, trained_models_dir):
        with pytest.raises(InvalidPredictionInputError, match="mapping"):
            ChurnPredictor(trained_models_dir).predict("C10293")  # type: ignore[arg-type]

    def test_non_numeric_value_in_numeric_field_raises(self, trained_models_dir, sample_customer):
        payload = dict(sample_customer)
        payload["MonthlyCharges"] = "not-a-number"
        with pytest.raises(InvalidPredictionInputError, match="MonthlyCharges"):
            ChurnPredictor(trained_models_dir).predict(payload)

    def test_blank_total_charges_with_zero_tenure_is_accepted(
        self, trained_models_dir, sample_customer
    ):
        payload = dict(sample_customer)
        payload["tenure"] = 0
        payload["TotalCharges"] = " "
        result = ChurnPredictor(trained_models_dir).predict(payload)
        assert set(result) == EXPECTED_KEYS

    def test_unknown_category_does_not_fail(self, trained_models_dir, sample_customer):
        payload = dict(sample_customer)
        payload["PaymentMethod"] = "Crypto wallet"
        result = ChurnPredictor(trained_models_dir).predict(payload)
        assert 0.0 <= result["churn_probability"] <= 1.0

    def test_key_order_does_not_change_result(self, trained_models_dir, sample_customer):
        predictor = ChurnPredictor(trained_models_dir)
        reordered = dict(reversed(list(sample_customer.items())))
        assert predictor.predict(reordered) == predictor.predict(sample_customer)

    def test_extra_columns_are_ignored(self, trained_models_dir, sample_customer):
        payload = dict(sample_customer)
        payload["unexpected_field"] = "ignored"
        result = ChurnPredictor(trained_models_dir).predict(payload)
        assert set(result) == EXPECTED_KEYS

    def test_batch_with_non_mapping_item_raises(self, trained_models_dir, sample_customer):
        with pytest.raises(InvalidPredictionInputError, match="index 1"):
            ChurnPredictor(trained_models_dir).predict_batch([sample_customer, "bad"])  # type: ignore[list-item]


class TestMissingArtifacts:
    def test_missing_model_raises(self, tmp_path, sample_customer):
        predictor = ChurnPredictor(tmp_path / "no-models-here")
        with pytest.raises(ModelArtifactNotFoundError, match="Train the model first"):
            predictor.predict(sample_customer)

    def test_partial_artifacts_raise(self, trained_models_dir, sample_customer):
        (trained_models_dir / config.PREPROCESSOR_FILENAME).unlink()
        with pytest.raises(ModelArtifactNotFoundError, match=config.PREPROCESSOR_FILENAME):
            ChurnPredictor(trained_models_dir).predict(sample_customer)

    def test_corrupt_metadata_raises(self, trained_models_dir, sample_customer):
        (trained_models_dir / config.METADATA_FILENAME).write_text("{not json", encoding="utf-8")
        with pytest.raises(MLPipelineError):
            ChurnPredictor(trained_models_dir).predict(sample_customer)


class TestMetadataContract:
    def test_metadata_exposes_feature_list(self, trained_models_dir):
        predictor = ChurnPredictor(trained_models_dir)
        assert predictor.feature_columns == list(config.FEATURE_COLUMNS)

    def test_metadata_is_readable_json(self, trained_models_dir):
        payload = json.loads(
            (trained_models_dir / config.METADATA_FILENAME).read_text(encoding="utf-8")
        )
        assert payload["target"] == config.TARGET_COLUMN
