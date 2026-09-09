"""Run one hypothetical profile through the existing model and explainer.

# =========================================================
# 1. WHAT THIS MODULE DOES — AND DOES NOT — CLAIM
# =========================================================

The simulator changes input features and observes how the *already trained*
model responds. Nothing is retrained, no second prediction pipeline exists, and
no treatment effect is estimated:

    current profile  -> saved model -> baseline probability
    hypothetical     -> same model  -> scenario probability

The difference between those two numbers is the model's sensitivity to the
changed features. It is not the effect of an intervention, and every piece of
text this module generates is worded accordingly.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from agent.models.scenario import Scenario
from agent.models.whatif import BaselinePrediction, DriverDelta, DriverSnapshot
from agent.simulation.feature_domain import FeatureDomain, domain_for
from agent.simulation.validator import build_hypothetical_profile
from ml.src.explainability.explainer import explain_customer
from ml.src.logging_config import get_logger
from ml.src.prediction.predictor import get_predictor

logger = get_logger(__name__)

# How many drivers each outcome reports for display. The comparison itself uses
# every feature, so this only controls the summary view.
TOP_DRIVER_DISPLAY_COUNT = 5

# Probability moves smaller than this are described as "essentially unchanged"
# rather than as a direction, because half a percentage point is not a signal a
# retention manager should act on.
NEGLIGIBLE_PROBABILITY_CHANGE = 0.005


@dataclass(frozen=True)
class ScenarioSimulation:
    """Raw simulation output for one scenario, before ranking is applied."""

    scenario: Scenario
    hypothetical_profile: dict[str, Any]
    baseline_probability: float
    scenario_probability: float
    baseline_risk_level: str
    scenario_risk_level: str
    baseline_drivers: list[DriverSnapshot]
    scenario_drivers: list[DriverSnapshot]
    driver_deltas: list[DriverDelta]
    interpretation: str

    @property
    def absolute_change(self) -> float:
        return round(self.scenario_probability - self.baseline_probability, 6)

    @property
    def relative_change(self) -> float:
        """Change as a fraction of the baseline estimate (0 when baseline is 0)."""
        if self.baseline_probability == 0:
            return 0.0
        return round(self.absolute_change / self.baseline_probability, 6)


# =========================================================
# 2. HELPERS
# =========================================================


def _to_snapshots(drivers: list[dict[str, Any]]) -> list[DriverSnapshot]:
    """Convert explainer output into typed snapshots."""
    return [DriverSnapshot(**driver) for driver in drivers]


def _describe_model_response(
    scenario: Scenario, baseline_probability: float, scenario_probability: float
) -> str:
    """Generate the non-causal wording for a scenario's result.

    Written by the system, never by the LLM, so the framing cannot drift into
    "this intervention reduces churn".
    """
    change = scenario_probability - baseline_probability
    percentage_points = change * 100
    movement = (
        f"{baseline_probability:.2%} to {scenario_probability:.2%} "
        f"({percentage_points:+.2f} percentage points)"
    )

    if abs(change) < NEGLIGIBLE_PROBABILITY_CHANGE:
        return (
            f"Under the '{scenario.scenario_name}' profile the trained model's churn "
            f"probability estimate is essentially unchanged: {movement}. The model is "
            "insensitive to this feature change for this customer."
        )

    direction = "lower" if change < 0 else "higher"
    return (
        f"Under the '{scenario.scenario_name}' profile the trained model estimates a "
        f"{direction} churn probability: {movement}. This reflects the model's "
        "sensitivity to the changed features, not a predicted effect of the intervention."
    )


def _build_driver_deltas(
    baseline_drivers: list[DriverSnapshot],
    scenario_drivers: list[DriverSnapshot],
    changed_features: tuple[str, ...],
) -> list[DriverDelta]:
    """Pair up baseline and scenario SHAP values feature by feature.

    Sorted by the size of the movement, because the interesting question is
    which contributions the profile change actually moved — often including
    features the scenario did not touch, since the model's linear score is
    shared across a one-hot block.
    """
    scenario_by_feature = {driver.feature: driver for driver in scenario_drivers}
    deltas: list[DriverDelta] = []

    for baseline_driver in baseline_drivers:
        scenario_driver = scenario_by_feature.get(baseline_driver.feature)
        if scenario_driver is None:
            continue
        deltas.append(
            DriverDelta(
                feature=baseline_driver.feature,
                baseline_shap=baseline_driver.shap_value,
                scenario_shap=scenario_driver.shap_value,
                shap_change=round(scenario_driver.shap_value - baseline_driver.shap_value, 6),
                changed_by_scenario=baseline_driver.feature in changed_features,
            )
        )

    deltas.sort(key=lambda delta: abs(delta.shap_change), reverse=True)
    return deltas


# =========================================================
# 3. THE SIMULATOR
# =========================================================


class WhatIfSimulator:
    """Evaluates hypothetical profiles against the saved model and explainer."""

    def __init__(self, models_dir: Path | str | None = None) -> None:
        self.models_dir = models_dir
        self._domain: FeatureDomain | None = None

    @property
    def domain(self) -> FeatureDomain:
        """Valid feature values, read from the fitted preprocessor."""
        if self._domain is None:
            self._domain = domain_for(self.models_dir)
        return self._domain

    def _explain(self, profile: Mapping[str, Any]) -> dict[str, Any]:
        """Predict and explain one profile using the existing Step 2/3 pipeline.

        ``explain_customer`` already calls the predictor internally and returns
        both the probability and the SHAP drivers, so this is a single pass — no
        duplicated preprocessing and no second prediction pipeline.

        Every original feature is requested (rather than a top-k slice) so the
        baseline and scenario explanations can be compared feature by feature.
        """
        feature_count = len(get_predictor(str(self.models_dir) if self.models_dir else None).feature_columns)
        return explain_customer(profile, top_k=feature_count, models_dir=self.models_dir)

    # =========================================================
    # 4. GENERATE BASELINE PREDICTION
    # =========================================================

    def baseline(
        self, customer_data: Mapping[str, Any]
    ) -> tuple[BaselinePrediction, dict[str, Any]]:
        """Predict and explain the customer's current, unmodified profile.

        Returns both the typed baseline and the raw explanation, because the
        scenario comparison needs the full driver list while the report only
        shows the top few.
        """
        explanation = self._explain(customer_data)
        drivers = _to_snapshots(explanation["top_drivers"])

        baseline = BaselinePrediction(
            churn_probability=explanation["churn_probability"],
            risk_level=explanation["risk_level"],
            prediction=explanation["prediction"],
            model_version=explanation.get("model_version", "unknown"),
            top_drivers=drivers[:TOP_DRIVER_DISPLAY_COUNT],
        )
        return baseline, explanation

    # =========================================================
    # 5. APPLY CHANGES, PREDICT, AND COMPARE
    # =========================================================

    def simulate(
        self,
        scenario: Scenario,
        customer_data: Mapping[str, Any],
        baseline_explanation: dict[str, Any] | None = None,
    ) -> ScenarioSimulation:
        """Evaluate one scenario for one customer.

        Args:
            scenario: The hypothetical profile change.
            customer_data: The customer's real record.
            baseline_explanation: Reuse of an explanation already computed for
                this customer, so a multi-scenario comparison predicts the
                baseline once rather than once per scenario.

        Raises:
            ScenarioValidationError: The scenario is invalid or inapplicable.
        """
        # --- 1. VALIDATE SCENARIO (raises before anything is predicted) --- #
        hypothetical_profile = build_hypothetical_profile(scenario, customer_data, self.domain)

        # --- 2. BASELINE --- #
        if baseline_explanation is None:
            baseline_explanation = self._explain(customer_data)

        # --- 3. SCENARIO PREDICTION, SAME MODEL AND PIPELINE --- #
        scenario_explanation = self._explain(hypothetical_profile)

        baseline_probability = float(baseline_explanation["churn_probability"])
        scenario_probability = float(scenario_explanation["churn_probability"])

        logger.info(
            "Scenario '%s': model estimate %.4f -> %.4f",
            scenario.scenario_id,
            baseline_probability,
            scenario_probability,
        )

        # --- 4. RISK BANDS (existing thresholds, taken from the predictor) --- #
        baseline_risk = str(baseline_explanation["risk_level"])
        scenario_risk = str(scenario_explanation["risk_level"])

        # --- 5. SHAP COMPARISON --- #
        baseline_drivers = _to_snapshots(baseline_explanation["top_drivers"])
        scenario_drivers = _to_snapshots(scenario_explanation["top_drivers"])
        driver_deltas = _build_driver_deltas(
            baseline_drivers, scenario_drivers, scenario.changed_feature_names
        )

        return ScenarioSimulation(
            scenario=scenario,
            hypothetical_profile=hypothetical_profile,
            baseline_probability=baseline_probability,
            scenario_probability=scenario_probability,
            baseline_risk_level=baseline_risk,
            scenario_risk_level=scenario_risk,
            baseline_drivers=baseline_drivers,
            scenario_drivers=scenario_drivers,
            driver_deltas=driver_deltas,
            interpretation=_describe_model_response(
                scenario, baseline_probability, scenario_probability
            ),
        )
