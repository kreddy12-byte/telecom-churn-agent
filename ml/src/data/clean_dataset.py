"""Deterministic, leakage-free data cleaning.

Only row-wise transformations live here. Anything that *learns* from data
(imputation values, scaling statistics, category vocabularies) belongs to the
scikit-learn pipeline in :mod:`ml.src.preprocessing.pipeline`, which is fitted on
the training split only.

Cleaning decisions applied to the IBM Telco dataset:

1. Whitespace is stripped from text columns; the raw CSV stores 11 blank
   ``TotalCharges`` values as `" "` rather than an empty field.
2. ``TotalCharges`` / ``MonthlyCharges`` / ``tenure`` are coerced to numeric.
   Unparseable values become ``NaN`` instead of being dropped.
3. Blank ``TotalCharges`` rows all have ``tenure == 0`` (brand-new customers who
   have not been billed yet), so they are set to ``0.0``. This is a domain rule
   applied identically at training and inference time, so it introduces no
   leakage. Any remaining ``NaN`` is imputed by the fitted pipeline.
4. Exact duplicate rows are removed and counted in the cleaning report.
5. The target is mapped ``No -> 0`` / ``Yes -> 1``; unknown labels raise.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from ml.src import config
from ml.src.exceptions import DatasetValidationError
from ml.src.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class CleaningReport:
    """What cleaning actually changed, for auditability."""

    rows_in: int
    rows_out: int
    duplicate_rows_removed: int = 0
    coerced_to_nan: dict[str, int] = field(default_factory=dict)
    zero_tenure_charges_filled: int = 0
    remaining_missing: dict[str, int] = field(default_factory=dict)
    target_distribution: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def strip_whitespace(frame: pd.DataFrame) -> pd.DataFrame:
    """Strip whitespace from text columns, turning blank strings into NaN.

    Non-string values are left untouched so the function stays idempotent and
    safe to reuse at inference time. ``np.nan`` is used rather than ``pd.NA``
    because scikit-learn imputers only recognise the former.
    """
    result = frame.copy()
    for column in result.columns:
        if result[column].dtype != object:
            continue
        stripped = result[column].map(
            lambda value: value.strip() if isinstance(value, str) else value
        )
        result[column] = stripped.map(lambda value: np.nan if value == "" else value)
    return result


def coerce_numeric_columns(
    frame: pd.DataFrame, columns: tuple[str, ...] | list[str] | None = None
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Coerce configured columns to numeric, returning per-column NaN counts."""
    target_columns = list(columns) if columns is not None else list(config.NUMERIC_COERCION_COLUMNS)
    result = frame.copy()
    coerced_counts: dict[str, int] = {}

    for column in target_columns:
        if column not in result.columns:
            continue
        before_missing = result[column].isna().sum()
        result[column] = pd.to_numeric(result[column], errors="coerce")
        new_nans = int(result[column].isna().sum() - before_missing)
        if new_nans > 0:
            coerced_counts[column] = new_nans

    return result, coerced_counts


def apply_domain_rules(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Apply leakage-free domain rules; returns the frame and rows affected."""
    result = frame.copy()
    filled = 0

    if {"tenure", "TotalCharges"}.issubset(result.columns):
        mask = result["TotalCharges"].isna() & (result["tenure"].fillna(-1) == 0)
        filled = int(mask.sum())
        if filled:
            result.loc[mask, "TotalCharges"] = 0.0

    return result, filled


def convert_target(series: pd.Series) -> pd.Series:
    """Map the churn label to a binary integer target.

    Raises:
        DatasetValidationError: When labels outside ``{No, Yes, 0, 1}`` appear.
    """
    normalized = series.astype(str).str.strip()
    mapped = normalized.map(config.TARGET_MAPPING)

    # Tolerate datasets that already store the target as 0/1.
    numeric_fallback = pd.to_numeric(normalized.where(mapped.isna()), errors="coerce")
    mapped = mapped.fillna(numeric_fallback)

    invalid_mask = mapped.isna() | ~mapped.isin([0, 1])
    if invalid_mask.any():
        invalid_values = sorted(normalized[invalid_mask].unique())
        raise DatasetValidationError(
            f"Target column '{config.TARGET_COLUMN}' contains invalid values: {invalid_values}. "
            f"Expected {sorted(config.TARGET_MAPPING)} or 0/1."
        )

    return mapped.astype(int)


def prepare_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the shared feature-side cleaning used by training *and* inference.

    Keeping this in one function guarantees the transformations applied to a
    single prediction request match those applied during training.
    """
    cleaned = strip_whitespace(frame)
    cleaned, _ = coerce_numeric_columns(cleaned)
    cleaned, _ = apply_domain_rules(cleaned)
    return cleaned


def clean_dataset(
    frame: pd.DataFrame, drop_duplicates: bool = True
) -> tuple[pd.DataFrame, CleaningReport]:
    """Clean the raw dataset and return the result plus an audit report."""
    rows_in = len(frame)
    cleaned = strip_whitespace(frame)
    cleaned, coerced_counts = coerce_numeric_columns(cleaned)
    cleaned, filled = apply_domain_rules(cleaned)

    duplicates_removed = 0
    if drop_duplicates:
        duplicate_mask = cleaned.duplicated()
        duplicates_removed = int(duplicate_mask.sum())
        if duplicates_removed:
            cleaned = cleaned.loc[~duplicate_mask].reset_index(drop=True)

    if config.TARGET_COLUMN in cleaned.columns:
        cleaned[config.TARGET_COLUMN] = convert_target(cleaned[config.TARGET_COLUMN])

    report = CleaningReport(
        rows_in=rows_in,
        rows_out=len(cleaned),
        duplicate_rows_removed=duplicates_removed,
        coerced_to_nan=coerced_counts,
        zero_tenure_charges_filled=filled,
        remaining_missing={
            str(column): int(count)
            for column, count in cleaned.isna().sum().items()
            if count > 0
        },
    )

    if config.TARGET_COLUMN in cleaned.columns:
        report.target_distribution = {
            str(label): int(count)
            for label, count in cleaned[config.TARGET_COLUMN].value_counts().items()
        }

    if coerced_counts:
        report.notes.append(f"Coerced non-numeric values to NaN: {coerced_counts}")
    if filled:
        report.notes.append(
            f"Set TotalCharges=0.0 for {filled} rows with tenure=0 (never billed)."
        )
    if duplicates_removed:
        report.notes.append(f"Removed {duplicates_removed} exact duplicate rows.")
    if report.remaining_missing:
        report.notes.append(
            "Remaining missing values are imputed inside the fitted preprocessing "
            f"pipeline (training statistics only): {report.remaining_missing}"
        )

    logger.info("Cleaning: %s rows in, %s rows out", report.rows_in, report.rows_out)
    for note in report.notes:
        logger.info("  %s", note)

    return cleaned, report
