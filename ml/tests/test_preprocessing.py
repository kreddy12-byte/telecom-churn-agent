"""Tests for feature separation and the preprocessing pipeline."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split

from ml.src import config
from ml.src.exceptions import DatasetValidationError
from ml.src.preprocessing.pipeline import (
    build_preprocessor,
    get_transformed_feature_names,
    resolve_feature_types,
    split_features_target,
)


class TestSplitFeaturesTarget:
    def test_excludes_id_and_target(self, cleaned_frame):
        features, target = split_features_target(cleaned_frame)
        assert config.ID_COLUMN not in features.columns
        assert config.TARGET_COLUMN not in features.columns
        assert len(features) == len(target)

    def test_feature_columns_match_config(self, cleaned_frame):
        features, _ = split_features_target(cleaned_frame)
        assert list(features.columns) == list(config.FEATURE_COLUMNS)

    def test_missing_target_raises(self, cleaned_frame):
        with pytest.raises(DatasetValidationError, match=config.TARGET_COLUMN):
            split_features_target(cleaned_frame.drop(columns=[config.TARGET_COLUMN]))

    def test_missing_feature_raises(self, cleaned_frame):
        with pytest.raises(DatasetValidationError, match="missing columns"):
            split_features_target(cleaned_frame.drop(columns=["Contract"]))


class TestResolveFeatureTypes:
    def test_types_are_partitioned(self, cleaned_frame):
        features, _ = split_features_target(cleaned_frame)
        numeric, categorical = resolve_feature_types(features)
        assert numeric == list(config.NUMERIC_FEATURES)
        assert categorical == list(config.CATEGORICAL_FEATURES)
        assert not set(numeric) & set(categorical)


class TestPreprocessor:
    @pytest.fixture
    def split_data(self, cleaned_frame):
        features, target = split_features_target(cleaned_frame)
        return train_test_split(
            features,
            target,
            test_size=config.TEST_SIZE,
            random_state=config.RANDOM_STATE,
            stratify=target,
        )

    def test_builds_column_transformer(self, cleaned_frame):
        features, _ = split_features_target(cleaned_frame)
        numeric, categorical = resolve_feature_types(features)
        preprocessor = build_preprocessor(numeric, categorical)
        assert isinstance(preprocessor, ColumnTransformer)
        assert [name for name, _, _ in preprocessor.transformers] == ["numeric", "categorical"]

    def test_fit_on_train_transform_on_test(self, split_data):
        x_train, x_test, _, _ = split_data
        numeric, categorical = resolve_feature_types(x_train)
        preprocessor = build_preprocessor(numeric, categorical)

        train_matrix = preprocessor.fit_transform(x_train)
        test_matrix = preprocessor.transform(x_test)

        assert train_matrix.shape[0] == len(x_train)
        assert test_matrix.shape[0] == len(x_test)
        assert train_matrix.shape[1] == test_matrix.shape[1]

    def test_output_has_no_missing_values(self, split_data):
        x_train, x_test, _, _ = split_data
        numeric, categorical = resolve_feature_types(x_train)
        preprocessor = build_preprocessor(numeric, categorical)
        preprocessor.fit(x_train)

        assert not np.isnan(np.asarray(preprocessor.transform(x_train), dtype=float)).any()
        assert not np.isnan(np.asarray(preprocessor.transform(x_test), dtype=float)).any()

    def test_numeric_features_are_scaled(self, split_data):
        x_train, _, _, _ = split_data
        numeric, categorical = resolve_feature_types(x_train)
        preprocessor = build_preprocessor(numeric, categorical)
        matrix = np.asarray(preprocessor.fit_transform(x_train), dtype=float)

        numeric_block = matrix[:, : len(numeric)]
        assert np.allclose(numeric_block.mean(axis=0), 0.0, atol=1e-6)
        assert np.allclose(numeric_block.std(axis=0), 1.0, atol=1e-6)

    def test_unseen_category_is_ignored_not_fatal(self, split_data):
        x_train, x_test, _, _ = split_data
        numeric, categorical = resolve_feature_types(x_train)
        preprocessor = build_preprocessor(numeric, categorical)
        preprocessor.fit(x_train)

        unseen = x_test.iloc[[0]].copy()
        unseen.loc[:, "Contract"] = "Quarterly-Special-Offer"
        transformed = preprocessor.transform(unseen)
        assert transformed.shape[1] == preprocessor.transform(x_test.iloc[[0]]).shape[1]

    def test_missing_numeric_value_is_imputed(self, split_data):
        x_train, x_test, _, _ = split_data
        numeric, categorical = resolve_feature_types(x_train)
        preprocessor = build_preprocessor(numeric, categorical)
        preprocessor.fit(x_train)

        row = x_test.iloc[[0]].copy()
        row.loc[:, "TotalCharges"] = np.nan
        transformed = np.asarray(preprocessor.transform(row), dtype=float)
        assert not np.isnan(transformed).any()

    def test_transformed_feature_names_match_width(self, split_data):
        x_train, _, _, _ = split_data
        numeric, categorical = resolve_feature_types(x_train)
        preprocessor = build_preprocessor(numeric, categorical)
        matrix = preprocessor.fit_transform(x_train)
        names = get_transformed_feature_names(preprocessor)
        assert len(names) == matrix.shape[1]

    def test_fitting_does_not_use_test_statistics(self, split_data):
        """Refitting on train only must give identical results regardless of test data."""
        x_train, x_test, _, _ = split_data
        numeric, categorical = resolve_feature_types(x_train)

        first = build_preprocessor(numeric, categorical).fit(x_train)
        second = build_preprocessor(numeric, categorical).fit(x_train)

        modified_test = x_test.copy()
        modified_test.loc[:, "MonthlyCharges"] = 9999.0

        np.testing.assert_allclose(
            np.asarray(first.transform(x_train), dtype=float),
            np.asarray(second.transform(x_train), dtype=float),
        )
        assert not np.isnan(
            np.asarray(first.transform(modified_test), dtype=float)
        ).any()

    def test_fitted_column_order_is_recorded(self, split_data):
        """The predictor relies on this to realign incoming records."""
        x_train, _, _, _ = split_data
        numeric, categorical = resolve_feature_types(x_train)
        preprocessor = build_preprocessor(numeric, categorical).fit(x_train)

        assert list(preprocessor.feature_names_in_) == list(x_train.columns)

    def test_single_row_transform(self, split_data):
        x_train, x_test, _, _ = split_data
        numeric, categorical = resolve_feature_types(x_train)
        preprocessor = build_preprocessor(numeric, categorical).fit(x_train)

        single = pd.DataFrame([x_test.iloc[0].to_dict()])
        assert preprocessor.transform(single).shape[0] == 1
