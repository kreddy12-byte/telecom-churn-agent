"""System and user prompts for the AI reasoning layer.

Design principle: **the model writes prose, the system owns every fact.**

The LLM is never asked to produce probabilities, SHAP values, strategy
definitions, or confidence. Those are supplied to it and re-attached by the
system afterwards. Its entire job is to turn structured evidence into a
personalised, readable recommendation and to justify the strategy choice. That
is what keeps the output grounded and what prevents this from being "ask ChatGPT
about a customer".
"""

from __future__ import annotations

import json

from agent.models.evidence import CustomerEvidence
from agent.models.strategy import StrategyEvaluation

# =========================================================
# 1. SYSTEM PROMPT — THE RULES THE MODEL MUST FOLLOW
# =========================================================

RETENTION_SYSTEM_PROMPT = """\
You are a retention analyst assistant for a telecom operator. You support human \
retention specialists; you never contact customers and never take actions yourself.

You are given machine learning evidence about one customer: a churn probability \
from a trained model, SHAP explanation values showing which features moved that \
prediction, the customer's profile, and a shortlist of pre-approved retention \
strategies that the business allows.

RULES YOU MUST FOLLOW:

1. Use ONLY the customer information supplied in the input. If a fact is not in \
the input, you do not know it and must not state it.
2. Never invent customer history, complaints, usage, competitor offers, or \
eligibility.
3. Never invent prices, discounts, percentages, monetary amounts, free items, or \
fee waivers. You may say a retention offer should be *considered* by a specialist, \
but you may not specify its terms.
4. Never guarantee an outcome. Do not say an intervention will prevent churn, \
retain the customer, or ensure any result.
5. SHAP values are evidence about how the MODEL reached its prediction. They are \
not proof of cause and effect. Never claim a feature causes churn; say it \
"contributes to the model's risk estimate" or similar.
6. Choose exactly one strategy, and only from the candidate strategies supplied \
in the input. Never invent a strategy or use one that is not listed.
7. Respect each strategy's stated allowed actions and contraindications.
8. Never claim you have performed an action. You cannot send email or SMS, change \
an account, apply a discount, or contact anyone.
9. Every recommendation requires human approval before anything happens.
10. Reply with a single JSON object and nothing else. No markdown, no code fences, \
no commentary before or after.

RESPONSE FORMAT (JSON object, exactly these keys):

{
  "strategy_id": "<one of the supplied candidate strategy_id values>",
  "recommendation": "<2-3 sentences addressed to the human retention specialist, \
describing the concrete next step for this specific customer>",
  "reasoning": ["<short evidence-based bullet>", "<another bullet>", "..."],
  "confidence": "<LOW | MEDIUM | HIGH>",
  "caveats": ["<optional: anything that makes you uncertain>"]
}

Keep "reasoning" to between 2 and 5 bullets, each referring to the supplied \
evidence. Your confidence is advisory only; the system computes its own and will \
never raise it based on your answer.\
"""


# =========================================================
# 2. USER PROMPT — THE STRUCTURED EVIDENCE
# =========================================================


def _describe_drivers(evidence: CustomerEvidence) -> list[dict]:
    """SHAP drivers, in the compact form given to the model."""
    return [
        {
            "feature": driver.feature,
            "customer_value": driver.value,
            "direction": driver.direction,
            "impact_share": round(driver.impact, 4),
            "shap_log_odds": round(driver.shap_value, 4),
        }
        for driver in evidence.top_drivers
    ]


def _describe_candidates(evaluation: StrategyEvaluation) -> list[dict]:
    """Candidate strategies, including the constraints the model must respect."""
    return [
        {
            "strategy_id": candidate.strategy.strategy_id,
            "name": candidate.strategy.name,
            "description": candidate.strategy.description,
            "objective": candidate.strategy.objective,
            "allowed_actions": list(candidate.strategy.allowed_actions),
            "contraindications": list(candidate.strategy.contraindications),
            "evidence_alignment_score": round(candidate.alignment_score, 4),
            "matched_risk_drivers": [driver.feature for driver in candidate.matched_drivers],
        }
        for candidate in evaluation.candidates
    ]


def build_reasoning_prompt(
    evidence: CustomerEvidence, evaluation: StrategyEvaluation
) -> str:
    """Serialise the evidence and candidate strategies into the user message.

    JSON is used rather than prose so the model receives unambiguous structure
    and so the exact payload can be logged and audited later.
    """
    payload = {
        "customer": {
            "customer_id": evidence.customer_id,
            "profile": evidence.customer_profile,
        },
        "model_prediction": {
            "churn_probability": evidence.churn_probability,
            "risk_level": evidence.risk_level,
            "predicted_class": evidence.prediction,
            "model_version": evidence.model_version,
        },
        "shap_explanation": {
            "explained_output": evidence.explained_output,
            "note": (
                "Positive shap_log_odds increases the model's churn risk estimate; "
                "negative decreases it. These describe model behaviour, not causation."
            ),
            "drivers": _describe_drivers(evidence),
        },
        "candidate_strategies": _describe_candidates(evaluation),
        "instruction": (
            "Select exactly one strategy_id from candidate_strategies and write a "
            "recommendation for the human retention specialist handling this account."
        ),
    }

    return json.dumps(payload, indent=2, default=str)
