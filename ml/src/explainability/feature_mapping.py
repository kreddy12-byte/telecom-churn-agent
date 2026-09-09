"""Map transformed (one-hot encoded) columns back to original features.

Why this module exists
----------------------
The fitted ``ColumnTransformer`` expands 19 original features into 45 transformed
columns, because every categorical feature becomes one column per category::

    Contract  ->  Contract_Month-to-month
                  Contract_One year
                  Contract_Two year

SHAP produces one value per *transformed* column. A reviewer or a customer
success agent needs "Contract", not "Contract_One year", so this module builds
the mapping between the two spaces.

The mapping is derived from the fitted encoder's ``categories_`` attribute, not
by splitting names on underscores. Splitting on "_" would break for category
values that contain underscores, and would silently produce wrong groupings.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.compose import ColumnTransformer

from ml.src.exceptions import MLPipelineError
from ml.src.logging_config import get_logger
from ml.src.preprocessing.pipeline import CATEGORICAL_STEP, NUMERIC_STEP

logger = get_logger(__name__)


@dataclass(frozen=True)
class TransformedFeature:
    """One column of the transformed matrix and where it came from."""

    index: int
    transformed_name: str
    original_feature: str
    category: str | None  # None for numeric columns

    @property
    def is_categorical(self) -> bool:
        return self.category is not None


def build_feature_map(preprocessor: ColumnTransformer) -> list[TransformedFeature]:
    """Describe every transformed column in terms of its original feature.

    Columns are emitted in the same order the ``ColumnTransformer`` produces
    them: all numeric columns first, then the one-hot blocks in feature order.
    """
    if not hasattr(preprocessor, "transformers_"):
        raise MLPipelineError(
            "Preprocessor is not fitted; cannot map transformed features back to "
            "original feature names."
        )

    feature_map: list[TransformedFeature] = []
    column_index = 0

    for step_name, transformer, columns in preprocessor.transformers_:
        if transformer == "drop" or not len(columns):
            continue

        if step_name == NUMERIC_STEP:
            # Numeric columns pass through imputation and scaling one-to-one.
            for column in columns:
                feature_map.append(
                    TransformedFeature(
                        index=column_index,
                        transformed_name=str(column),
                        original_feature=str(column),
                        category=None,
                    )
                )
                column_index += 1

        elif step_name == CATEGORICAL_STEP:
            encoder = transformer.named_steps["encoder"]
            # categories_[i] holds the categories learned for columns[i], in the
            # exact order the encoder emits them.
            for column, categories in zip(columns, encoder.categories_, strict=True):
                for category in categories:
                    feature_map.append(
                        TransformedFeature(
                            index=column_index,
                            transformed_name=f"{column}_{category}",
                            original_feature=str(column),
                            category=str(category),
                        )
                    )
                    column_index += 1

        else:  # pragma: no cover - guards against future transformer additions
            raise MLPipelineError(
                f"Unknown transformer step '{step_name}' in the preprocessor; "
                "the feature map must be updated before SHAP can be trusted."
            )

    _verify_against_sklearn_names(preprocessor, feature_map)
    return feature_map


def _verify_against_sklearn_names(
    preprocessor: ColumnTransformer, feature_map: list[TransformedFeature]
) -> None:
    """Cross-check our mapping against scikit-learn's own output names.

    This is a cheap safety net: if scikit-learn ever changes column ordering,
    the explanation would attach SHAP values to the wrong features, which is far
    worse than failing loudly.
    """
    try:
        sklearn_names = [str(name) for name in preprocessor.get_feature_names_out()]
    except (AttributeError, ValueError) as exc:  # pragma: no cover - version guard
        logger.warning("Could not cross-check transformed feature names: %s", exc)
        return

    if len(sklearn_names) != len(feature_map):
        raise MLPipelineError(
            f"Feature map has {len(feature_map)} columns but the preprocessor reports "
            f"{len(sklearn_names)}. Refusing to produce a misaligned explanation."
        )

    mismatches = [
        (expected, mapped.transformed_name)
        for expected, mapped in zip(sklearn_names, feature_map, strict=True)
        if expected != mapped.transformed_name
    ]
    if mismatches:
        raise MLPipelineError(
            "Transformed feature names do not line up with the preprocessor output. "
            f"First mismatch: {mismatches[0]}."
        )


def group_indices_by_feature(
    feature_map: list[TransformedFeature],
) -> dict[str, list[int]]:
    """Return ``{original_feature: [transformed column indices]}``."""
    groups: dict[str, list[int]] = {}
    for feature in feature_map:
        groups.setdefault(feature.original_feature, []).append(feature.index)
    return groups


def aggregate_shap_by_feature(
    shap_values: np.ndarray, groups: dict[str, list[int]]
) -> dict[str, float]:
    """Aggregate transformed-space SHAP values into original-feature values.

    Aggregation strategy: **sum** the SHAP values of all columns belonging to the
    same original feature.

    Why summing is the defensible choice: SHAP values are additive, meaning
    ``model_output = base_value + sum(all shap values)``. Summing a feature's
    encoded columns therefore yields exactly that feature's total contribution
    to the model output, and the additive property still holds after grouping.
    Averaging or taking the maximum would break additivity and understate the
    contribution of features with many categories.

    Note that for a one-hot block only one column equals 1 while the others
    equal 0, but the zero columns still carry non-zero SHAP values (they encode
    "this customer is *not* on a two-year contract"). Summing correctly folds
    that information into the single reported feature.

    Args:
        shap_values: SHAP values for one customer, shape ``(n_transformed,)``.
        groups: Output of :func:`group_indices_by_feature`.

    Returns:
        ``{original_feature: signed aggregated SHAP value}``.
    """
    values = np.asarray(shap_values).ravel()

    expected_width = sum(len(indices) for indices in groups.values())
    if values.size != expected_width:
        raise MLPipelineError(
            f"Received {values.size} SHAP values but the feature map describes "
            f"{expected_width} transformed columns."
        )

    return {
        feature: float(values[indices].sum()) for feature, indices in groups.items()
    }


def aggregate_shap_matrix(
    shap_matrix: np.ndarray, groups: dict[str, list[int]]
) -> dict[str, np.ndarray]:
    """Vectorised version of :func:`aggregate_shap_by_feature` for many rows.

    Args:
        shap_matrix: SHAP values of shape ``(n_customers, n_transformed)``.
        groups: Output of :func:`group_indices_by_feature`.

    Returns:
        ``{original_feature: array of per-customer aggregated SHAP values}``.
    """
    matrix = np.atleast_2d(np.asarray(shap_matrix))

    expected_width = sum(len(indices) for indices in groups.values())
    if matrix.shape[1] != expected_width:
        raise MLPipelineError(
            f"SHAP matrix has {matrix.shape[1]} columns but the feature map describes "
            f"{expected_width} transformed columns."
        )

    return {
        feature: matrix[:, indices].sum(axis=1) for feature, indices in groups.items()
    }
