"""Tests for the SHAP explainability layer.

These tests never download the dataset and never fake SHAP values: the fixtures
train a small but real Logistic Regression on synthetic data using the same
preprocessing architecture as production, then explain it with the real
``shap.LinearExplainer``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ml.src import config
from ml.src.exceptions import (
    InvalidPredictionInputError,
    MLPipelineError,
    ModelArtifactNotFoundError,
)
from ml.src.explainability.explainer import (
    DIRECTION_DECREASES,
    DIRECTION_INCREASES,
    EXPLAINED_OUTPUT,
    ChurnExplainer,
)
from ml.src.explainability.feature_mapping import (
    aggregate_shap_by_feature,
    aggregate_shap_matrix,
    build_feature_map,
    group_indices_by_feature,
)
from ml.src.explainability.global_importance import (
    compute_global_importance,
    save_global_importance,
)
from ml.src.explainability.plots import plot_customer_explanation, plot_global_importance

VALID_DIRECTIONS = {DIRECTION_INCREASES, DIRECTION_DECREASES}
EXPLANATION_KEYS = {
    "customer_id",
    "churn_probability",
    "prediction",
    "risk_level",
    "model_version",
    "explained_output",
    "base_value",
    "top_drivers",
}


# =========================================================
# 1. EXPLAINER LOADS CORRECTLY
# =========================================================


class TestExplainerLoading:
    def test_loads_without_error(self, explainer):
        explainer.load()
        assert explainer.transformed_feature_count > 0

    def test_uses_linear_explainer(self, explainer):
        import shap

        explainer.load()
        assert isinstance(explainer._explainer, shap.LinearExplainer)

    def test_base_value_is_finite(self, explainer):
        assert np.isfinite(explainer.base_value)

    def test_transformed_feature_count_matches_preprocessor(self, explainer):
        explainer.load()
        preprocessor = explainer.predictor.preprocessor
        assert explainer.transformed_feature_count == len(preprocessor.get_feature_names_out())

    def test_loading_is_idempotent(self, explainer):
        explainer.load()
        first = explainer._explainer
        explainer.load()
        assert explainer._explainer is first

    def test_missing_artifacts_raise_useful_error(self, tmp_path, sample_customer):
        empty_explainer = ChurnExplainer(models_dir=tmp_path / "no-artifacts")
        with pytest.raises(ModelArtifactNotFoundError, match="Train the model first"):
            empty_explainer.explain(sample_customer)

    def test_stale_background_is_rejected(self, trained_models_dir, sample_customer):
        wrong_width_background = np.zeros((10, 3))
        stale = ChurnExplainer(
            models_dir=trained_models_dir, background=wrong_width_background
        )
        with pytest.raises(MLPipelineError, match="stale"):
            stale.explain(sample_customer)


# =========================================================
# 2-3. VALID CUSTOMER PRODUCES AN EXPLANATION WITH DRIVERS
# =========================================================


class TestExplanationOutput:
    def test_returns_expected_keys(self, explainer, sample_customer):
        explanation = explainer.explain(sample_customer)
        assert set(explanation) == EXPLANATION_KEYS

    def test_contains_top_drivers(self, explainer, sample_customer):
        drivers = explainer.explain(sample_customer)["top_drivers"]
        assert isinstance(drivers, list)
        assert len(drivers) > 0

    def test_driver_fields(self, explainer, sample_customer):
        for driver in explainer.explain(sample_customer)["top_drivers"]:
            assert set(driver) == {"feature", "value", "impact", "direction", "shap_value"}

    def test_probability_matches_prediction_interface(self, explainer, sample_customer):
        explanation = explainer.explain(sample_customer)
        prediction = explainer.predictor.predict(sample_customer)
        assert explanation["churn_probability"] == prediction["churn_probability"]
        assert explanation["risk_level"] == prediction["risk_level"]

    def test_customer_id_is_echoed_when_supplied(self, explainer, sample_customer):
        explanation = explainer.explain(sample_customer)
        assert explanation["customer_id"] == sample_customer[config.ID_COLUMN]

    def test_customer_id_is_none_when_absent(self, explainer, sample_customer):
        anonymous = {
            key: value for key, value in sample_customer.items() if key != config.ID_COLUMN
        }
        assert explainer.explain(anonymous)["customer_id"] is None

    def test_declares_the_output_scale(self, explainer, sample_customer):
        assert explainer.explain(sample_customer)["explained_output"] == EXPLAINED_OUTPUT

    def test_impact_is_a_bounded_share(self, explainer, sample_customer):
        """impact must stay in [0, 1] to satisfy the backend RiskDriver schema."""
        drivers = explainer.explain(sample_customer, top_k=19)["top_drivers"]
        assert all(0.0 <= driver["impact"] <= 1.0 for driver in drivers)
        assert sum(driver["impact"] for driver in drivers) == pytest.approx(1.0, abs=0.01)

    def test_explanation_is_deterministic(self, explainer, sample_customer):
        assert explainer.explain(sample_customer) == explainer.explain(sample_customer)

    def test_explain_many(self, explainer, raw_frame):
        records = raw_frame.drop(columns=[config.TARGET_COLUMN]).head(3).to_dict("records")
        explanations = explainer.explain_many(records)
        assert len(explanations) == 3


# =========================================================
# 4. top_k BEHAVIOUR
# =========================================================


class TestTopK:
    def test_default_is_five(self, explainer, sample_customer):
        assert len(explainer.explain(sample_customer)["top_drivers"]) == 5

    @pytest.mark.parametrize("top_k", [1, 3, 7])
    def test_respects_requested_size(self, explainer, sample_customer, top_k):
        drivers = explainer.explain(sample_customer, top_k=top_k)["top_drivers"]
        assert len(drivers) == top_k

    def test_caps_at_available_features(self, explainer, sample_customer):
        drivers = explainer.explain(sample_customer, top_k=500)["top_drivers"]
        assert len(drivers) == len(config.FEATURE_COLUMNS)

    def test_zero_or_negative_raises(self, explainer, sample_customer):
        with pytest.raises(InvalidPredictionInputError, match="top_k"):
            explainer.explain(sample_customer, top_k=0)


# =========================================================
# 5-6. ORDERING AND DIRECTION
# =========================================================


class TestOrderingAndDirection:
    def test_sorted_by_absolute_impact(self, explainer, sample_customer):
        drivers = explainer.explain(sample_customer, top_k=10)["top_drivers"]
        impacts = [driver["impact"] for driver in drivers]
        assert impacts == sorted(impacts, reverse=True)

    def test_top_driver_has_largest_absolute_shap(self, explainer, sample_customer):
        drivers = explainer.explain(sample_customer, top_k=19)["top_drivers"]
        magnitudes = [abs(driver["shap_value"]) for driver in drivers]
        assert magnitudes[0] == max(magnitudes)

    def test_directions_are_valid(self, explainer, sample_customer):
        drivers = explainer.explain(sample_customer, top_k=19)["top_drivers"]
        assert {driver["direction"] for driver in drivers} <= VALID_DIRECTIONS

    def test_direction_follows_shap_sign(self, explainer, sample_customer):
        """Direction must be derived from SHAP, not from domain intuition."""
        for driver in explainer.explain(sample_customer, top_k=19)["top_drivers"]:
            expected = (
                DIRECTION_INCREASES if driver["shap_value"] > 0 else DIRECTION_DECREASES
            )
            assert driver["direction"] == expected

    def test_both_directions_can_occur(self, explainer, raw_frame):
        """A real explanation contains protective as well as risky factors."""
        records = raw_frame.drop(columns=[config.TARGET_COLUMN]).head(10).to_dict("records")
        observed = {
            driver["direction"]
            for record in records
            for driver in explainer.explain(record, top_k=19)["top_drivers"]
        }
        assert observed == VALID_DIRECTIONS


# =========================================================
# 7. INVALID INPUT
# =========================================================


class TestInvalidInput:
    def test_missing_feature_names_the_field(self, explainer, sample_customer):
        incomplete = dict(sample_customer)
        incomplete.pop("Contract")
        with pytest.raises(InvalidPredictionInputError, match="Contract"):
            explainer.explain(incomplete)

    def test_non_mapping_input_raises(self, explainer):
        with pytest.raises(InvalidPredictionInputError, match="mapping"):
            explainer.explain("7590-VHVEG")  # type: ignore[arg-type]

    def test_empty_mapping_raises(self, explainer):
        with pytest.raises(InvalidPredictionInputError):
            explainer.explain({})

    def test_unparseable_numeric_raises(self, explainer, sample_customer):
        payload = dict(sample_customer)
        payload["MonthlyCharges"] = "abc"
        with pytest.raises(InvalidPredictionInputError, match="MonthlyCharges"):
            explainer.explain(payload)


# =========================================================
# 8-9. SHAP VALUES COME FROM THE ACTUAL MODEL
# =========================================================


class TestShapFidelity:
    def test_additivity_holds(self, explainer, sample_customer):
        """base_value + sum(SHAP) must reproduce the model's log-odds exactly."""
        _, transformed = explainer.predictor.transform_customers([sample_customer])
        explainer.verify_additivity(transformed)

    def test_additivity_matches_decision_function(self, explainer, sample_customer):
        _, transformed = explainer.predictor.transform_customers([sample_customer])
        shap_values = explainer._compute_shap_values(transformed)

        reconstructed = shap_values.sum(axis=1) + explainer.base_value
        actual = explainer.predictor.model.decision_function(transformed)
        np.testing.assert_allclose(reconstructed, actual, atol=1e-8)

    def test_shap_equals_linear_contribution(self, explainer, sample_customer):
        """For a linear model, SHAP = coefficient * (value - background mean)."""
        _, transformed = explainer.predictor.transform_customers([sample_customer])
        shap_values = explainer._compute_shap_values(transformed)[0]

        coefficients = np.asarray(explainer.predictor.model.coef_).ravel()
        background_mean = explainer.background.mean(axis=0)
        expected = coefficients * (transformed[0] - background_mean)

        np.testing.assert_allclose(shap_values, expected, atol=1e-8)

    def test_changing_a_feature_changes_the_explanation(self, explainer, sample_customer):
        monthly = dict(sample_customer)
        monthly["Contract"] = "Month-to-month"
        two_year = dict(sample_customer)
        two_year["Contract"] = "Two year"

        contract_shap = []
        for payload in (monthly, two_year):
            drivers = explainer.explain(payload, top_k=19)["top_drivers"]
            contract_shap.append(
                next(d["shap_value"] for d in drivers if d["feature"] == "Contract")
            )
        assert contract_shap[0] != contract_shap[1]

    def test_zero_contribution_when_customer_equals_background_mean(self, explainer):
        """Sanity check on the SHAP definition: no deviation means no contribution."""
        background_mean = explainer.background.mean(axis=0, keepdims=True)
        shap_values = explainer._compute_shap_values(background_mean)
        np.testing.assert_allclose(shap_values, 0.0, atol=1e-8)


# =========================================================
# 10. FEATURE NAME MAPPING
# =========================================================


class TestFeatureMapping:
    def test_map_covers_every_transformed_column(self, explainer):
        explainer.load()
        preprocessor = explainer.predictor.preprocessor
        feature_map = build_feature_map(preprocessor)
        assert len(feature_map) == len(preprocessor.get_feature_names_out())

    def test_map_names_match_sklearn(self, explainer):
        explainer.load()
        preprocessor = explainer.predictor.preprocessor
        mapped = [item.transformed_name for item in build_feature_map(preprocessor)]
        assert mapped == [str(name) for name in preprocessor.get_feature_names_out()]

    def test_numeric_columns_map_one_to_one(self, explainer):
        explainer.load()
        feature_map = build_feature_map(explainer.predictor.preprocessor)
        numeric = [item for item in feature_map if not item.is_categorical]
        assert [item.original_feature for item in numeric] == list(config.NUMERIC_FEATURES)

    def test_categorical_columns_group_under_original_feature(self, explainer):
        explainer.load()
        feature_map = build_feature_map(explainer.predictor.preprocessor)
        contract_columns = [
            item for item in feature_map if item.original_feature == "Contract"
        ]
        assert len(contract_columns) == 3
        assert {item.category for item in contract_columns} == {
            "Month-to-month",
            "One year",
            "Two year",
        }

    def test_groups_cover_all_original_features(self, explainer):
        explainer.load()
        groups = group_indices_by_feature(build_feature_map(explainer.predictor.preprocessor))
        assert set(groups) == set(config.FEATURE_COLUMNS)

    def test_drivers_use_original_feature_names(self, explainer, sample_customer):
        """No transformed names such as 'Contract_Two year' may leak to callers."""
        drivers = explainer.explain(sample_customer, top_k=19)["top_drivers"]
        assert {driver["feature"] for driver in drivers} <= set(config.FEATURE_COLUMNS)

    def test_driver_value_is_the_original_value(self, explainer, sample_customer):
        drivers = explainer.explain(sample_customer, top_k=19)["top_drivers"]
        contract_driver = next(d for d in drivers if d["feature"] == "Contract")
        assert contract_driver["value"] == sample_customer["Contract"]

    def test_aggregation_sums_group_members(self):
        groups = {"numeric_feature": [0], "categorical_feature": [1, 2, 3]}
        shap_values = np.array([0.5, 0.2, -0.7, 0.1])
        aggregated = aggregate_shap_by_feature(shap_values, groups)
        assert aggregated["numeric_feature"] == pytest.approx(0.5)
        assert aggregated["categorical_feature"] == pytest.approx(-0.4)

    def test_aggregation_preserves_additivity(self, explainer, sample_customer):
        """Grouping must not change the total contribution."""
        _, transformed = explainer.predictor.transform_customers([sample_customer])
        shap_values = explainer._compute_shap_values(transformed)[0]
        groups = group_indices_by_feature(explainer.feature_map)

        aggregated = aggregate_shap_by_feature(shap_values, groups)
        assert sum(aggregated.values()) == pytest.approx(float(shap_values.sum()))

    def test_aggregation_rejects_wrong_width(self):
        with pytest.raises(MLPipelineError, match="SHAP values"):
            aggregate_shap_by_feature(np.array([1.0, 2.0]), {"a": [0, 1, 2]})

    def test_matrix_aggregation_matches_row_aggregation(self, explainer, feature_frame):
        explainer.load()
        rows = feature_frame.head(4)
        prepared = explainer.predictor.validate_input(rows)
        transformed = np.asarray(explainer.predictor.preprocessor.transform(prepared))
        shap_matrix = explainer._compute_shap_values(transformed)
        groups = group_indices_by_feature(explainer.feature_map)

        matrix_result = aggregate_shap_matrix(shap_matrix, groups)
        first_row_result = aggregate_shap_by_feature(shap_matrix[0], groups)

        for feature, values in matrix_result.items():
            assert values[0] == pytest.approx(first_row_result[feature])


# =========================================================
# 11. GLOBAL FEATURE IMPORTANCE
# =========================================================


class TestGlobalImportance:
    def test_report_has_required_columns(self, explainer, feature_frame):
        report = compute_global_importance(explainer, feature_frame.head(50))
        assert list(report.columns) == ["feature", "mean_absolute_shap", "mean_signed_shap"]

    def test_report_covers_every_feature(self, explainer, feature_frame):
        report = compute_global_importance(explainer, feature_frame.head(50))
        assert set(report["feature"]) == set(config.FEATURE_COLUMNS)

    def test_sorted_descending(self, explainer, feature_frame):
        report = compute_global_importance(explainer, feature_frame.head(50))
        values = report["mean_absolute_shap"].tolist()
        assert values == sorted(values, reverse=True)

    def test_absolute_importance_is_non_negative(self, explainer, feature_frame):
        report = compute_global_importance(explainer, feature_frame.head(50))
        assert (report["mean_absolute_shap"] >= 0).all()

    def test_saves_csv(self, explainer, feature_frame, tmp_path):
        report = compute_global_importance(explainer, feature_frame.head(20))
        path = save_global_importance(report, models_dir=tmp_path)
        assert path.exists()

        reloaded = pd.read_csv(path)
        assert len(reloaded) == len(config.FEATURE_COLUMNS)
        assert "mean_absolute_shap" in reloaded.columns

    def test_shap_by_feature_shape(self, explainer, feature_frame):
        rows = feature_frame.head(12)
        result = explainer.shap_by_feature(rows)
        assert result.shape == (12, len(config.FEATURE_COLUMNS))


# =========================================================
# VISUALISATION
# =========================================================


class TestPlots:
    def test_global_plot_is_written(self, explainer, feature_frame, tmp_path):
        report = compute_global_importance(explainer, feature_frame.head(20))
        path = plot_global_importance(report, models_dir=tmp_path)
        assert path.exists() and path.stat().st_size > 0

    def test_customer_plot_is_written(self, explainer, sample_customer, tmp_path):
        explanation = explainer.explain(sample_customer)
        path = plot_customer_explanation(explanation, models_dir=tmp_path)
        assert path.exists() and path.stat().st_size > 0

    def test_customer_plot_requires_drivers(self, tmp_path):
        with pytest.raises(ValueError, match="no drivers"):
            plot_customer_explanation({"top_drivers": []}, models_dir=tmp_path)
