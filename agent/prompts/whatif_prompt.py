"""Prompt for the what-if interpretation layer.

The division of labour from Step 4 holds exactly: the system has already run
every scenario, computed every probability, produced every SHAP value, and
ranked the results. The model is handed those finished numbers and asked only to
read them back for a retention manager.

The largest risk here is not fabrication but *framing* — a fluent model will
naturally write "this offer would cut churn by 16%", which is a causal claim the
simulation does not support. The prompt states the allowed phrasing explicitly,
and ``agent/guardrails.py`` verifies the answer complied.
"""

from __future__ import annotations

import json

from agent.models.whatif import WhatIfResult

# =========================================================
# 1. SYSTEM PROMPT
# =========================================================

WHATIF_SYSTEM_PROMPT = """\
You are a retention analyst assistant for a telecom operator. You are reviewing \
the output of a what-if simulation that has ALREADY been run by the system.

The system took a customer's real profile, changed one or more features to create \
hypothetical profiles, and ran each through the same trained churn model. You are \
given the resulting probabilities, risk levels, SHAP explanations, and the \
system's own ranking. Your job is to interpret these results for a human \
retention manager.

WHAT THIS SIMULATION IS:
Measuring how the trained model's probability estimate responds to hypothetical \
feature values.

WHAT IT IS NOT:
An estimate of what an intervention would do to real customer behaviour. Nothing \
here establishes cause and effect.

RULES YOU MUST FOLLOW:

1. Never state or imply that an intervention will reduce, prevent, or stop churn. \
Do not write "reduces churn", "prevents churn", or "churn reduction".
2. Correct phrasing is: "the trained model estimates a lower churn probability \
under this hypothetical profile". Always attribute the change to the MODEL'S \
ESTIMATE, never to the customer's behaviour.
3. Never invent, alter, or restate a probability, percentage, SHAP value, or \
ranking score. The system owns every number; you interpret them in words. Do not \
put numbers in your answer that were not supplied to you.
4. Never invent prices, discounts, offer terms, eligibility, or customer facts.
5. Only discuss the scenarios supplied. Never invent a scenario.
6. If an intervention is listed as not simulatable, say so plainly rather than \
guessing at its effect.
7. Treat SHAP values as model evidence, not causal evidence.
8. Every result requires human approval; you cannot take any action.
9. Reply with a single JSON object and nothing else. No markdown, no code fences.

RESPONSE FORMAT (JSON object, exactly these keys):

{
  "most_promising_scenario_id": "<the scenario_id the model results most support, \
or null if none do>",
  "interpretation": "<3-5 sentences for the retention manager: what the model \
results show, whether they line up with the customer's strongest risk drivers, \
and how much weight to put on them>",
  "considerations": ["<what the human reviewer should check or think about before \
approving>", "..."],
  "caveats": ["<optional: anything that makes these results less trustworthy for \
this customer>"]
}

Keep "considerations" to between 2 and 5 items.\
"""


# =========================================================
# 2. USER PROMPT — THE FINISHED SIMULATION RESULTS
# =========================================================


def _describe_baseline(result: WhatIfResult) -> dict:
    return {
        "churn_probability": result.baseline.churn_probability,
        "risk_level": result.baseline.risk_level,
        "model_version": result.baseline.model_version,
        "top_shap_drivers": [
            {
                "feature": driver.feature,
                "customer_value": driver.value,
                "shap_log_odds": driver.shap_value,
                "direction": driver.direction,
                "impact_share": driver.impact,
            }
            for driver in result.baseline.top_drivers
        ],
    }


def _describe_scenarios(result: WhatIfResult) -> list[dict]:
    """Finished scenario results, including the SHAP movement behind each one."""
    return [
        {
            "scenario_id": outcome.scenario_id,
            "scenario_name": outcome.scenario_name,
            "strategy_id": outcome.strategy_id,
            "changed_features": outcome.changed_features,
            "baseline_probability": outcome.baseline_probability,
            "scenario_probability": outcome.scenario_probability,
            "percentage_point_change": outcome.percentage_point_change,
            "baseline_risk_level": outcome.baseline_risk_level,
            "scenario_risk_level": outcome.scenario_risk_level,
            "ranking_score": outcome.ranking_score,
            "ranking_factors": outcome.ranking_factors.model_dump(),
            "conflicts_with_evidence": outcome.conflicts_with_evidence,
            "conflict_reason": outcome.conflict_reason,
            "largest_shap_movements": [
                {
                    "feature": delta.feature,
                    "baseline_shap": delta.baseline_shap,
                    "scenario_shap": delta.scenario_shap,
                    "shap_change": delta.shap_change,
                }
                for delta in outcome.driver_deltas
            ],
            "scenario_limitations": outcome.limitations,
        }
        for outcome in result.scenarios
    ]


def build_whatif_prompt(result: WhatIfResult) -> str:
    """Serialise the completed simulation into the user message."""
    payload = {
        "customer": {
            "customer_id": result.customer_id,
            "profile": result.customer_profile,
        },
        "baseline_prediction": _describe_baseline(result),
        "candidate_retention_strategies": result.candidate_strategy_ids,
        "scenario_results": _describe_scenarios(result),
        "scenarios_not_applicable": [
            {"scenario_id": rejection.scenario_id, "reason": rejection.reason}
            for rejection in result.rejected_scenarios
        ],
        "interventions_that_cannot_be_simulated": [
            {
                "strategy_id": item.strategy_id,
                "intervention": item.intervention,
                "reason": item.reason,
            }
            for item in result.unsimulatable_interventions
        ],
        "system_ranking": {
            "recommended_scenario_id": result.recommended_scenario_id,
            "selection_reason": result.selection_reason,
            "methodology": result.ranking_methodology,
        },
        "instruction": (
            "Interpret these completed results for the retention manager. Do not "
            "recalculate anything and do not introduce numbers of your own."
        ),
    }
    return json.dumps(payload, indent=2, default=str)
