"""Dataset loading and validation.

Validation is split into *blocking* problems (raise :class:`DatasetValidationError`)
and *observations* that are reported but handled downstream by cleaning, so no
problematic data is silently discarded.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from ml.src import config
from ml.src.exceptions import DatasetNotFoundError, DatasetValidationError
from ml.src.logging_config import configure_logging, get_logger

logger = get_logger(__name__)


@dataclass
class ValidationReport:
    """Structured summary of dataset health."""

    path: str
    n_rows: int
    n_columns: int
    columns: list[str]
    dtypes: dict[str, str]
    missing_columns: list[str] = field(default_factory=list)
    duplicate_rows: int = 0
    duplicate_ids: int = 0
    missing_values: dict[str, int] = field(default_factory=dict)
    blank_string_counts: dict[str, int] = field(default_factory=dict)
    non_numeric_values: dict[str, int] = field(default_factory=dict)
    negative_values: dict[str, int] = field(default_factory=dict)
    target_distribution: dict[str, int] = field(default_factory=dict)
    invalid_target_values: list[str] = field(default_factory=list)
    numeric_columns: list[str] = field(default_factory=list)
    categorical_columns: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def load_raw_dataset(path: Path | str | None = None) -> pd.DataFrame:
    """Load the raw CSV into a DataFrame.

    Raises:
        DatasetNotFoundError: When the CSV is missing.
        DatasetValidationError: When the file is empty or unparseable.
    """
    csv_path = Path(path) if path else config.RAW_DATASET_PATH

    if not csv_path.exists():
        raise DatasetNotFoundError(
            f"Dataset not found at {csv_path}. "
            "Run `python -m ml.src.data.download_dataset` first."
        )

    try:
        frame = pd.read_csv(csv_path)
    except pd.errors.EmptyDataError as exc:
        raise DatasetValidationError(f"Dataset at {csv_path} is empty: {exc}") from exc
    except pd.errors.ParserError as exc:
        raise DatasetValidationError(f"Dataset at {csv_path} is not valid CSV: {exc}") from exc

    if frame.empty:
        raise DatasetValidationError(f"Dataset at {csv_path} contains no rows.")

    logger.info("Loaded dataset %s with shape %s", csv_path, frame.shape)
    return frame


def _count_blank_strings(series: pd.Series) -> int:
    if series.dtype != object:
        return 0
    return int(series.astype(str).str.strip().eq("").sum())


def _count_non_numeric(series: pd.Series) -> int:
    """Count values that cannot be parsed as numbers (excluding true NaNs)."""
    coerced = pd.to_numeric(series, errors="coerce")
    return int((coerced.isna() & series.notna()).sum())


def validate_dataset(
    frame: pd.DataFrame,
    path: Path | str | None = None,
    strict: bool = True,
) -> ValidationReport:
    """Validate the raw dataset and return a structured report.

    Args:
        frame: Raw dataset.
        path: Source path, recorded in the report for traceability.
        strict: When True, blocking problems raise ``DatasetValidationError``.

    Blocking problems: empty dataset, missing required columns, missing target
    column, and target values outside the expected label set.
    """
    source = str(path) if path else str(config.RAW_DATASET_PATH)

    report = ValidationReport(
        path=source,
        n_rows=int(len(frame)),
        n_columns=int(frame.shape[1]),
        columns=[str(column) for column in frame.columns],
        dtypes={str(column): str(dtype) for column, dtype in frame.dtypes.items()},
    )

    blocking: list[str] = []

    if frame.empty:
        blocking.append("Dataset contains no rows.")

    report.missing_columns = [
        column for column in config.REQUIRED_COLUMNS if column not in frame.columns
    ]
    if report.missing_columns:
        blocking.append(f"Missing required columns: {report.missing_columns}")

    # Target checks
    if config.TARGET_COLUMN in frame.columns:
        target = frame[config.TARGET_COLUMN]
        report.target_distribution = {
            str(label): int(count) for label, count in target.value_counts(dropna=False).items()
        }
        observed = {str(value).strip() for value in target.dropna().unique()}
        expected = set(config.TARGET_MAPPING) | {"0", "1"}
        report.invalid_target_values = sorted(observed - expected)
        if report.invalid_target_values:
            blocking.append(
                f"Target column '{config.TARGET_COLUMN}' contains unexpected values: "
                f"{report.invalid_target_values}"
            )
        if target.isna().any():
            blocking.append(
                f"Target column '{config.TARGET_COLUMN}' contains "
                f"{int(target.isna().sum())} missing values."
            )
    else:
        blocking.append(f"Target column '{config.TARGET_COLUMN}' is missing.")

    # Structural observations
    report.duplicate_rows = int(frame.duplicated().sum())
    if config.ID_COLUMN in frame.columns:
        report.duplicate_ids = int(frame[config.ID_COLUMN].duplicated().sum())

    report.missing_values = {
        str(column): int(count)
        for column, count in frame.isna().sum().items()
        if count > 0
    }
    report.blank_string_counts = {
        str(column): _count_blank_strings(frame[column])
        for column in frame.columns
        if _count_blank_strings(frame[column]) > 0
    }

    report.numeric_columns = [
        column for column in config.NUMERIC_FEATURES if column in frame.columns
    ]
    report.categorical_columns = [
        column for column in config.CATEGORICAL_FEATURES if column in frame.columns
    ]

    for column in config.NUMERIC_COERCION_COLUMNS:
        if column not in frame.columns:
            continue
        non_numeric = _count_non_numeric(frame[column])
        if non_numeric:
            report.non_numeric_values[column] = non_numeric

    for column in config.NON_NEGATIVE_COLUMNS:
        if column not in frame.columns:
            continue
        coerced = pd.to_numeric(frame[column], errors="coerce")
        negatives = int((coerced < 0).sum())
        if negatives:
            report.negative_values[column] = negatives

    # Non-blocking warnings
    if report.duplicate_rows:
        report.warnings.append(f"{report.duplicate_rows} exact duplicate rows detected.")
    if report.duplicate_ids:
        report.warnings.append(f"{report.duplicate_ids} duplicate {config.ID_COLUMN} values.")
    for column, count in report.non_numeric_values.items():
        report.warnings.append(
            f"{count} non-numeric values in '{column}' will be coerced to NaN and imputed "
            "using training-set statistics."
        )
    for column, count in report.negative_values.items():
        report.warnings.append(f"{count} negative values in '{column}' — review required.")
    if report.missing_values:
        report.warnings.append(f"Missing values present: {report.missing_values}")

    if blocking and strict:
        raise DatasetValidationError(
            "Dataset validation failed:\n" + "\n".join(f"  - {issue}" for issue in blocking)
        )
    report.warnings.extend(blocking)
    return report


def log_dataset_summary(report: ValidationReport) -> None:
    """Log a human-readable dataset summary."""
    logger.info("Dataset summary for %s", report.path)
    logger.info("  Rows: %s | Columns: %s", report.n_rows, report.n_columns)
    logger.info("  Numeric features: %s", report.numeric_columns)
    logger.info("  Categorical features: %s", report.categorical_columns)
    logger.info("  Target distribution: %s", report.target_distribution)

    total = sum(report.target_distribution.values()) or 1
    for label, count in report.target_distribution.items():
        logger.info("    %s: %s (%.2f%%)", label, count, 100 * count / total)

    logger.info("  Duplicate rows: %s | Duplicate IDs: %s", report.duplicate_rows, report.duplicate_ids)
    logger.info("  Missing values: %s", report.missing_values or "none")
    logger.info("  Blank strings: %s", report.blank_string_counts or "none")
    logger.info("  Non-numeric in numeric columns: %s", report.non_numeric_values or "none")

    for warning in report.warnings:
        logger.warning("  %s", warning)


def validate_dataset_file(path: Path | str | None = None) -> ValidationReport:
    """Load and validate the dataset in one call."""
    csv_path = Path(path) if path else config.RAW_DATASET_PATH
    frame = load_raw_dataset(csv_path)
    report = validate_dataset(frame, path=csv_path)
    log_dataset_summary(report)
    return report


def main() -> int:
    configure_logging()
    parser = argparse.ArgumentParser(description="Validate the raw churn dataset.")
    parser.add_argument("--path", default=None, help="Path to the raw CSV.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    args = parser.parse_args()

    try:
        report = validate_dataset_file(args.path)
    except (DatasetNotFoundError, DatasetValidationError) as exc:
        logger.error("%s", exc)
        return 1

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
