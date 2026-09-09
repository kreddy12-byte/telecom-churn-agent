"""The set of feature values the trained model actually understands.

# =========================================================
# 1. WHY THIS MODULE EXISTS
# =========================================================

A what-if scenario is only meaningful if the hypothetical profile is one the
model could have seen during training. ``Contract = "12 months"`` is not a
smaller version of ``Contract = "One year"`` — it is a category the encoder never
learned, and ``handle_unknown="ignore"`` would quietly encode it as all-zeros,
producing a confident-looking prediction from a profile that means nothing.

So the domain is read from the *fitted* preprocessor rather than hardcoded:
whatever the model was trained on is, by definition, what it understands.

# =========================================================
# 2. STRUCTURAL CONSTRAINTS
# =========================================================

The Telco dataset also encodes dependencies between features. A customer without
internet has ``TechSupport = "No internet service"``, not ``"No"``. Simulating
``TechSupport = "Yes"`` for such a customer would produce a profile that cannot
exist, so those combinations are rejected. The rules below were verified against
all 7,043 rows of the raw dataset and hold without exception.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from ml.src.explainability.feature_mapping import build_feature_map
from ml.src.prediction.predictor import ChurnPredictor, get_predictor

# Features that cannot be negative in the source data.
NON_NEGATIVE_NUMERIC: frozenset[str] = frozenset({"tenure", "MonthlyCharges", "TotalCharges"})

# Numeric features that are really binary flags.
BINARY_NUMERIC: dict[str, tuple[float, ...]] = {"SeniorCitizen": (0.0, 1.0)}

INTERNET_ADDONS: tuple[str, ...] = (
    "OnlineSecurity",
    "OnlineBackup",
    "DeviceProtection",
    "TechSupport",
    "StreamingTV",
    "StreamingMovies",
)


@dataclass(frozen=True)
class DependencyRule:
    """A structural relationship between features in the source data."""

    driver_feature: str
    driver_value: str
    dependent_features: tuple[str, ...]
    required_value: str
    description: str


STRUCTURAL_RULES: tuple[DependencyRule, ...] = (
    DependencyRule(
        driver_feature="InternetService",
        driver_value="No",
        dependent_features=INTERNET_ADDONS,
        required_value="No internet service",
        description="internet add-ons are only defined for customers who have internet",
    ),
    DependencyRule(
        driver_feature="PhoneService",
        driver_value="No",
        dependent_features=("MultipleLines",),
        required_value="No phone service",
        description="multiple lines are only defined for customers who have phone service",
    ),
)


# =========================================================
# 3. THE DOMAIN ITSELF
# =========================================================


@dataclass(frozen=True)
class FeatureDomain:
    """Valid values for every feature the model consumes."""

    feature_order: tuple[str, ...]
    numeric_features: frozenset[str]
    categorical_values: dict[str, tuple[str, ...]]

    def is_known_feature(self, feature: str) -> bool:
        return feature in self.feature_order

    def is_categorical(self, feature: str) -> bool:
        return feature in self.categorical_values

    def is_numeric(self, feature: str) -> bool:
        return feature in self.numeric_features

    def allowed_values(self, feature: str) -> tuple[str, ...]:
        """Categories learned for a categorical feature."""
        return self.categorical_values.get(feature, ())


def build_feature_domain(predictor: ChurnPredictor) -> FeatureDomain:
    """Read the learned feature domain out of the fitted preprocessor."""
    feature_map = build_feature_map(predictor.preprocessor)

    categorical_values: dict[str, list[str]] = {}
    for transformed in feature_map:
        if transformed.category is None:
            continue
        categorical_values.setdefault(transformed.original_feature, []).append(
            transformed.category
        )

    return FeatureDomain(
        feature_order=tuple(predictor.feature_columns),
        numeric_features=frozenset(predictor.numeric_features),
        categorical_values={
            feature: tuple(categories) for feature, categories in categorical_values.items()
        },
    )


@lru_cache(maxsize=4)
def get_feature_domain(models_dir: str | None = None) -> FeatureDomain:
    """Cached domain for the saved artifacts (the preprocessor never changes)."""
    return build_feature_domain(get_predictor(models_dir))


def domain_for(models_dir: Path | str | None = None) -> FeatureDomain:
    """Convenience wrapper accepting a Path."""
    return get_feature_domain(str(models_dir) if models_dir else None)


# =========================================================
# 4. VALUE AND CONSISTENCY CHECKS
# =========================================================


def check_value(feature: str, value: Any, domain: FeatureDomain) -> str | None:
    """Return a rejection reason, or None when the value is usable.

    Categorical values must be one of the learned categories. Numeric values must
    be finite numbers, respecting the small number of domain constraints the
    source data guarantees.
    """
    if not domain.is_known_feature(feature):
        return (
            f"'{feature}' is not a feature of the trained model. "
            f"Known features: {list(domain.feature_order)}."
        )

    if domain.is_categorical(feature):
        allowed = domain.allowed_values(feature)
        if not isinstance(value, str) or value not in allowed:
            return (
                f"'{value}' is not a value the model learned for '{feature}'. "
                f"Allowed values: {list(allowed)}."
            )
        return None

    # Numeric feature.
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return f"'{feature}' is numeric, but the scenario supplied {type(value).__name__}."
    if not math.isfinite(float(value)):
        return f"'{feature}' must be a finite number, got {value}."
    if feature in NON_NEGATIVE_NUMERIC and float(value) < 0:
        return f"'{feature}' cannot be negative, got {value}."
    if feature in BINARY_NUMERIC and float(value) not in BINARY_NUMERIC[feature]:
        return (
            f"'{feature}' is a binary flag; allowed values are "
            f"{list(BINARY_NUMERIC[feature])}, got {value}."
        )
    return None


def check_profile_consistency(profile: dict[str, Any]) -> list[str]:
    """Return every structural contradiction in a (hypothetical) profile.

    Applied to the profile *after* the scenario's changes, so a scenario that
    switches on an add-on for a customer with no internet is caught.
    """
    violations: list[str] = []

    for rule in STRUCTURAL_RULES:
        driver_value = profile.get(rule.driver_feature)
        if driver_value is None:
            continue
        driver_matches = str(driver_value).strip() == rule.driver_value

        for dependent in rule.dependent_features:
            if dependent not in profile:
                continue
            dependent_value = str(profile[dependent]).strip()

            if driver_matches and dependent_value != rule.required_value:
                violations.append(
                    f"{dependent}='{dependent_value}' is impossible when "
                    f"{rule.driver_feature}='{rule.driver_value}' "
                    f"({rule.description}); it must be '{rule.required_value}'."
                )
            elif not driver_matches and dependent_value == rule.required_value:
                violations.append(
                    f"{dependent}='{rule.required_value}' is impossible when "
                    f"{rule.driver_feature}='{driver_value}' ({rule.description})."
                )

    return violations
