"""Tests for dataset loading, validation, target conversion, and cleaning."""

from __future__ import annotations

import pandas as pd
import pytest

from ml.src import config
from ml.src.data.clean_dataset import clean_dataset, convert_target, prepare_feature_frame
from ml.src.data.validate_dataset import load_raw_dataset, validate_dataset
from ml.src.exceptions import DatasetNotFoundError, DatasetValidationError


class TestLoadRawDataset:
    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(DatasetNotFoundError, match="download_dataset"):
            load_raw_dataset(tmp_path / "does_not_exist.csv")

    def test_empty_file_raises(self, tmp_path):
        empty = tmp_path / "empty.csv"
        empty.write_text("", encoding="utf-8")
        with pytest.raises(DatasetValidationError):
            load_raw_dataset(empty)

    def test_loads_valid_csv(self, tmp_path, raw_frame):
        path = tmp_path / "telco.csv"
        raw_frame.to_csv(path, index=False)
        loaded = load_raw_dataset(path)
        assert len(loaded) == len(raw_frame)
        assert config.TARGET_COLUMN in loaded.columns


class TestValidateDataset:
    def test_valid_dataset_passes(self, raw_frame):
        report = validate_dataset(raw_frame)
        assert report.n_rows == len(raw_frame)
        assert report.missing_columns == []
        assert set(report.target_distribution) <= {"Yes", "No"}
        assert report.numeric_columns == list(config.NUMERIC_FEATURES)

    def test_missing_required_column_raises(self, raw_frame):
        frame = raw_frame.drop(columns=["Contract"])
        with pytest.raises(DatasetValidationError, match="Missing required columns"):
            validate_dataset(frame)

    def test_missing_target_column_raises(self, raw_frame):
        frame = raw_frame.drop(columns=[config.TARGET_COLUMN])
        with pytest.raises(DatasetValidationError, match=config.TARGET_COLUMN):
            validate_dataset(frame)

    def test_invalid_target_values_raise(self, raw_frame):
        frame = raw_frame.copy()
        frame.loc[0, config.TARGET_COLUMN] = "Maybe"
        with pytest.raises(DatasetValidationError, match="unexpected values"):
            validate_dataset(frame)

    def test_empty_dataframe_raises(self, raw_frame):
        with pytest.raises(DatasetValidationError):
            validate_dataset(raw_frame.iloc[0:0])

    def test_non_strict_mode_reports_instead_of_raising(self, raw_frame):
        frame = raw_frame.drop(columns=["Contract"])
        report = validate_dataset(frame, strict=False)
        assert "Contract" in report.missing_columns
        assert any("Missing required columns" in warning for warning in report.warnings)

    def test_duplicates_are_counted(self, raw_frame):
        frame = pd.concat([raw_frame, raw_frame.iloc[[0]]], ignore_index=True)
        report = validate_dataset(frame)
        assert report.duplicate_rows == 1
        assert report.duplicate_ids == 1

    def test_blank_total_charges_detected(self, raw_frame):
        report = validate_dataset(raw_frame)
        assert report.non_numeric_values.get("TotalCharges", 0) > 0

    def test_negative_values_reported(self, raw_frame):
        frame = raw_frame.copy()
        frame.loc[1, "MonthlyCharges"] = -10.0
        report = validate_dataset(frame)
        assert report.negative_values.get("MonthlyCharges") == 1


class TestConvertTarget:
    def test_yes_no_mapping(self):
        converted = convert_target(pd.Series(["Yes", "No", "Yes"]))
        assert converted.tolist() == [1, 0, 1]

    def test_whitespace_is_tolerated(self):
        converted = convert_target(pd.Series([" Yes", "No "]))
        assert converted.tolist() == [1, 0]

    def test_already_binary_is_preserved(self):
        converted = convert_target(pd.Series([0, 1, 1]))
        assert converted.tolist() == [0, 1, 1]

    def test_invalid_label_raises(self):
        with pytest.raises(DatasetValidationError, match="invalid values"):
            convert_target(pd.Series(["Yes", "Unknown"]))

    def test_output_dtype_is_int(self, raw_frame):
        converted = convert_target(raw_frame[config.TARGET_COLUMN])
        assert converted.dtype.kind == "i"


class TestCleanDataset:
    def test_target_becomes_binary(self, raw_frame):
        cleaned, _ = clean_dataset(raw_frame)
        assert set(cleaned[config.TARGET_COLUMN].unique()) <= {0, 1}

    def test_total_charges_is_numeric(self, raw_frame):
        cleaned, _ = clean_dataset(raw_frame)
        assert pd.api.types.is_numeric_dtype(cleaned["TotalCharges"])

    def test_zero_tenure_charges_filled_with_zero(self, raw_frame):
        cleaned, report = clean_dataset(raw_frame)
        zero_tenure = cleaned[cleaned["tenure"] == 0]
        assert report.zero_tenure_charges_filled > 0
        assert (zero_tenure["TotalCharges"] == 0.0).all()

    def test_duplicates_removed_and_reported(self, raw_frame):
        frame = pd.concat([raw_frame, raw_frame.iloc[[0]]], ignore_index=True)
        cleaned, report = clean_dataset(frame)
        assert report.duplicate_rows_removed == 1
        assert len(cleaned) == len(raw_frame)

    def test_no_rows_dropped_without_duplicates(self, raw_frame):
        cleaned, report = clean_dataset(raw_frame)
        assert report.rows_in == report.rows_out == len(raw_frame)

    def test_cleaning_notes_document_decisions(self, raw_frame):
        _, report = clean_dataset(raw_frame)
        assert any("tenure=0" in note for note in report.notes)

    def test_prepare_feature_frame_is_idempotent(self, raw_frame):
        once = prepare_feature_frame(raw_frame)
        twice = prepare_feature_frame(once)
        pd.testing.assert_frame_equal(once, twice)
