"""Shared fixtures for agent tests.

The evidence fixtures are synthetic but structurally identical to real
``explain_customer`` output, so unit tests never need the model artifacts or the
dataset. The end-to-end test in ``test_integration_pipeline.py`` is the one place
that uses the real trained model.
"""

from __future__ import annotations

import json

import pytest

from agent.models.evidence import CustomerEvidence
from agent.models.whatif import (
    BaselinePrediction,
    DriverSnapshot,
    RankingFactors,
    ScenarioOutcome,
    WhatIfResult,
)
from agent.providers.base import LLMCompletion, LLMProvider
from agent.simulation.feature_domain import FeatureDomain


# =========================================================
# 1. STUB LLM PROVIDER (NO NETWORK, NO PAID API CALLS)
# =========================================================


class StubProvider(LLMProvider):
    """Returns canned text, or raises a canned error, instead of calling an API."""

    name = "stub"

    def __init__(
        self,
        response_text: str = "",
        error: Exception | None = None,
        available: bool = True,
        model: str = "stub-model",
    ) -> None:
        self.response_text = response_text
        self.error = error
        self.available = available
        self.model = model
        self.calls: list[tuple[str, str]] = []

    def is_available(self) -> bool:
        return self.available

    def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        self.calls.append((system_prompt, user_prompt))
        if self.error is not None:
            raise self.error
        return LLMCompletion(text=self.response_text, model=self.model, provider=self.name)


def make_llm_payload(
    strategy_id: str = "EARLY_LIFECYCLE_ONBOARDING",
    recommendation: str = (
        "Arrange a personalised onboarding call for this recently joined customer and "
        "walk them through the services included in their plan. Route the account to a "
        "retention specialist for approval before making contact."
    ),
    reasoning: list[str] | None = None,
    confidence: str | None = "HIGH",
    caveats: list[str] | None = None,
) -> str:
    """Build a well-formed LLM reply for tests."""
    payload: dict = {
        "strategy_id": strategy_id,
        "recommendation": recommendation,
        "reasoning": reasoning
        or [
            "The model estimates a high churn probability for this customer.",
            "Short tenure is the strongest risk-increasing driver in the explanation.",
        ],
    }
    if confidence is not None:
        payload["confidence"] = confidence
    if caveats is not None:
        payload["caveats"] = caveats
    return json.dumps(payload)


# =========================================================
# 2. EVIDENCE FIXTURES
# =========================================================


@pytest.fixture
def high_risk_evidence() -> CustomerEvidence:
    """A short-tenure, month-to-month customer with several risk drivers."""
    return CustomerEvidence(
        customer_id="TEST-HIGH-01",
        churn_probability=0.87,
        risk_level="HIGH",
        prediction=1,
        model_version="1.0.0",
        top_drivers=[
            {
                "feature": "tenure",
                "value": 1,
                "impact": 0.35,
                "direction": "increases_risk",
                "shap_value": 1.24,
            },
            {
                "feature": "MonthlyCharges",
                "value": 70.35,
                "impact": 0.20,
                "direction": "increases_risk",
                "shap_value": 0.71,
            },
            {
                "feature": "InternetService",
                "value": "DSL",
                "impact": 0.18,
                "direction": "decreases_risk",
                "shap_value": -0.64,
            },
            {
                "feature": "Contract",
                "value": "Month-to-month",
                "impact": 0.15,
                "direction": "increases_risk",
                "shap_value": 0.53,
            },
            {
                "feature": "TotalCharges",
                "value": 29.85,
                "impact": 0.12,
                "direction": "decreases_risk",
                "shap_value": -0.42,
            },
        ],
        customer_profile={
            "customerID": "TEST-HIGH-01",
            "tenure": 1,
            "Contract": "Month-to-month",
            "MonthlyCharges": 70.35,
            "TotalCharges": 29.85,
            "InternetService": "DSL",
            "TechSupport": "No",
            "PaymentMethod": "Electronic check",
        },
    )


@pytest.fixture
def low_risk_evidence() -> CustomerEvidence:
    """A long-tenured customer on the longest contract."""
    return CustomerEvidence(
        customer_id="TEST-LOW-01",
        churn_probability=0.12,
        risk_level="LOW",
        prediction=0,
        model_version="1.0.0",
        top_drivers=[
            {
                "feature": "Contract",
                "value": "Two year",
                "impact": 0.45,
                "direction": "decreases_risk",
                "shap_value": -1.60,
            },
            {
                "feature": "tenure",
                "value": 60,
                "impact": 0.30,
                "direction": "decreases_risk",
                "shap_value": -1.05,
            },
            {
                "feature": "TechSupport",
                "value": "No",
                "impact": 0.10,
                "direction": "increases_risk",
                "shap_value": 0.35,
            },
        ],
        customer_profile={
            "customerID": "TEST-LOW-01",
            "tenure": 60,
            "Contract": "Two year",
            "MonthlyCharges": 45.10,
            "TechSupport": "No",
        },
    )


# =========================================================
# 3. WHAT-IF FIXTURES
# =========================================================


@pytest.fixture
def feature_domain() -> FeatureDomain:
    """The trained model's feature domain, without loading the model.

    Mirrors what ``build_feature_domain`` reads out of the fitted preprocessor.
    ``test_whatif_simulation.py`` asserts this fixture still matches the real
    artifacts, so unit tests stay fast without silently drifting.
    """
    return FeatureDomain(
        feature_order=(
            "SeniorCitizen",
            "tenure",
            "MonthlyCharges",
            "TotalCharges",
            "gender",
            "Partner",
            "Dependents",
            "PhoneService",
            "MultipleLines",
            "InternetService",
            "OnlineSecurity",
            "OnlineBackup",
            "DeviceProtection",
            "TechSupport",
            "StreamingTV",
            "StreamingMovies",
            "Contract",
            "PaperlessBilling",
            "PaymentMethod",
        ),
        numeric_features=frozenset({"SeniorCitizen", "tenure", "MonthlyCharges", "TotalCharges"}),
        categorical_values={
            "gender": ("Female", "Male"),
            "Partner": ("No", "Yes"),
            "Dependents": ("No", "Yes"),
            "PhoneService": ("No", "Yes"),
            "MultipleLines": ("No", "No phone service", "Yes"),
            "InternetService": ("DSL", "Fiber optic", "No"),
            "OnlineSecurity": ("No", "No internet service", "Yes"),
            "OnlineBackup": ("No", "No internet service", "Yes"),
            "DeviceProtection": ("No", "No internet service", "Yes"),
            "TechSupport": ("No", "No internet service", "Yes"),
            "StreamingTV": ("No", "No internet service", "Yes"),
            "StreamingMovies": ("No", "No internet service", "Yes"),
            "Contract": ("Month-to-month", "One year", "Two year"),
            "PaperlessBilling": ("No", "Yes"),
            "PaymentMethod": (
                "Bank transfer (automatic)",
                "Credit card (automatic)",
                "Electronic check",
                "Mailed check",
            ),
        },
    )


@pytest.fixture
def customer_profile() -> dict:
    """A complete, structurally valid customer record (month-to-month, has internet)."""
    return {
        "customerID": "TEST-WHATIF-01",
        "gender": "Female",
        "SeniorCitizen": 0,
        "Partner": "Yes",
        "Dependents": "No",
        "tenure": 1,
        "PhoneService": "No",
        "MultipleLines": "No phone service",
        "InternetService": "DSL",
        "OnlineSecurity": "No",
        "OnlineBackup": "Yes",
        "DeviceProtection": "No",
        "TechSupport": "No",
        "StreamingTV": "No",
        "StreamingMovies": "No",
        "Contract": "Month-to-month",
        "PaperlessBilling": "Yes",
        "PaymentMethod": "Electronic check",
        "MonthlyCharges": 29.85,
        "TotalCharges": 29.85,
    }


@pytest.fixture
def no_internet_profile(customer_profile: dict) -> dict:
    """A customer without internet, where add-ons are 'No internet service'."""
    profile = dict(customer_profile)
    profile.update(
        {
            "PhoneService": "Yes",
            "MultipleLines": "No",
            "InternetService": "No",
            "OnlineSecurity": "No internet service",
            "OnlineBackup": "No internet service",
            "DeviceProtection": "No internet service",
            "TechSupport": "No internet service",
            "StreamingTV": "No internet service",
            "StreamingMovies": "No internet service",
        }
    )
    return profile


def make_scenario_outcome(
    scenario_id: str,
    scenario_probability: float,
    ranking_score: float,
    strategy_id: str = "CONTRACT_CONVERSION",
    baseline_probability: float = 0.80,
    conflicts_with_evidence: bool = False,
) -> ScenarioOutcome:
    """Build a synthetic outcome for ranking/selection tests."""
    change = round(scenario_probability - baseline_probability, 6)
    return ScenarioOutcome(
        scenario_id=scenario_id,
        scenario_name=scenario_id.replace("_", " ").title(),
        strategy_id=strategy_id,
        description="Synthetic scenario used in tests.",
        rationale="Synthetic rationale.",
        changed_features={"Contract": "One year"},
        baseline_probability=baseline_probability,
        scenario_probability=scenario_probability,
        absolute_probability_change=change,
        relative_probability_change=round(change / baseline_probability, 6),
        percentage_point_change=round(change * 100, 2),
        baseline_risk_level="HIGH",
        scenario_risk_level="HIGH",
        risk_level_changed=False,
        ranking_score=ranking_score,
        ranking_factors=RankingFactors(
            model_response=0.2,
            evidence_alignment=0.1,
            driver_targeting=0.1,
            conflict_penalty_applied=conflicts_with_evidence,
        ),
        conflicts_with_evidence=conflicts_with_evidence,
        conflict_reason="synthetic conflict" if conflicts_with_evidence else None,
        model_based_interpretation="Synthetic model-based interpretation.",
    )


@pytest.fixture
def whatif_result(customer_profile: dict) -> WhatIfResult:
    """A completed deterministic what-if result, ready for the AI layer."""
    return WhatIfResult(
        customer_id="TEST-WHATIF-01",
        customer_profile=customer_profile,
        baseline=BaselinePrediction(
            churn_probability=0.8064,
            risk_level="HIGH",
            prediction=1,
            model_version="1.0.0",
            top_drivers=[
                DriverSnapshot(
                    feature="tenure",
                    value=1,
                    shap_value=1.3752,
                    direction="increases_risk",
                    impact=0.2768,
                )
            ],
        ),
        candidate_strategy_ids=["CONTRACT_CONVERSION", "GENERAL_RETENTION_REVIEW"],
        scenarios=[
            make_scenario_outcome("two_year_contract", 0.4984, 0.2320),
            make_scenario_outcome("annual_contract", 0.6675, 0.1272),
        ],
        recommended_scenario_id="two_year_contract",
        selection_reason="Synthetic selection reason.",
        ranking_methodology="Synthetic methodology.",
    )


@pytest.fixture
def evidence_without_drivers() -> CustomerEvidence:
    """Evidence where the SHAP layer returned nothing usable."""
    return CustomerEvidence(
        customer_id="TEST-EMPTY-01",
        churn_probability=0.55,
        risk_level="MEDIUM",
        prediction=1,
        model_version="1.0.0",
        top_drivers=[],
        customer_profile={"customerID": "TEST-EMPTY-01", "tenure": 24},
    )
