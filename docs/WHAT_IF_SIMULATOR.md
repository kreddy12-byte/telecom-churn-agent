# What-If Retention Simulator

## 1. Purpose

The agent layer (Step 4) answers *"what should we consider doing for this
customer?"*. This layer answers a narrower, more testable question:

> If this customer's profile had different values, what would the **already
> trained** model predict?

That is a question about model sensitivity, and it is the only question a
what-if simulator built on a churn classifier can honestly answer. The value for
a retention manager is that it turns "contract type is an important driver" into
"under a two-year contract profile the model's estimate falls from 80.64% to
49.84%, and the contract contribution is the only thing that moves".

---

## 2. Architecture

```
customer record
      ↓
baseline prediction + SHAP        ml/src/prediction, ml/src/explainability  (Steps 2–3)
      ↓
customer evidence                 agent/models/evidence.py                  (Step 4)
      ↓
eligible retention strategies     agent/strategies/evaluator.py             (Step 4)
      ↓
scenario validation               agent/simulation/validator.py
      ↓
scenario prediction + SHAP        agent/simulation/simulator.py   (same model, no retraining)
      ↓
transparent ranking               agent/simulation/ranking.py
      ↓
AI interpretation                 agent/services/scenario_interpretation_service.py
      ↓
human approval
```

| Module | Responsibility |
|---|---|
| `agent/models/scenario.py` | `Scenario`, `UnsimulatableIntervention` |
| `agent/models/whatif.py` | `WhatIfResult`, `ScenarioOutcome`, SHAP snapshots and deltas |
| `agent/simulation/feature_domain.py` | Valid feature values, read from the fitted preprocessor |
| `agent/simulation/catalogue.py` | Approved scenarios and unsimulatable interventions |
| `agent/simulation/validator.py` | Feature, applicability, and structural checks |
| `agent/simulation/simulator.py` | Baseline and scenario prediction with SHAP |
| `agent/simulation/ranking.py` | The scoring formula |
| `agent/simulation/comparison.py` | Multi-scenario comparison engine |
| `agent/simulation/report.py` | Human-readable rendering |
| `agent/services/whatif_service.py` | End-to-end orchestration |
| `agent/whatif_cli.py` | `python -m agent.whatif_cli` |

Nothing is retrained, no second prediction pipeline exists, and no additional
model artifact is produced. The simulator calls the same `explain_customer()`
entry point the rest of the system uses, which internally calls the same
`ChurnPredictor`.

---

## 3. Methodology, and why this is not causal inference

The simulation is a **sensitivity analysis of a fitted function**:

```
f = trained logistic regression ∘ fitted preprocessor

baseline  = f(x)
scenario  = f(x')      where x' differs from x in one or more features
```

`scenario − baseline` is the model's response to a different input. Calling it
the effect of an intervention would require three things this project does not
have:

1. **Exchangeability.** Customers on two-year contracts differ systematically
   from month-to-month customers in ways the dataset does not capture. The model
   has learned that association, not a mechanism.
2. **A treatment.** The dataset records contract type, not the act of converting
   someone's contract. Nobody in the training data was intervened upon.
3. **Counterfactual validity.** `f(x')` is the prediction for a customer who
   *looks like* `x'`, not for this customer *after* being moved to `x'`.

So the wording is fixed throughout the codebase:

| Allowed | Forbidden |
|---|---|
| "Under this hypothetical profile the trained model estimates a lower churn probability." | "This offer will reduce churn by 16%." |
| "The model's estimate falls by 30.80 percentage points." | "A 30.80% churn reduction." |
| "Contract contributes to the model's risk estimate." | "The contract causes churn." |

Every result carries the disclaimer **"Model-based what-if estimate — not a
causal prediction."**, and `agent/guardrails.py` has a `causal_effect_claim` rule
that rejects LLM prose slipping into the forbidden column. The rule is
context-aware: "lowers the churn **probability estimate**" passes, "lowers
churn" does not.

---

## 4. Baseline prediction

The baseline is produced by `explain_customer()`, which internally calls the
existing predictor — so the baseline probability, predicted class, risk band, and
model version are identical to what `POST /api/predict` will return. There is no
separate baseline code path to drift out of sync.

The simulator requests **every** original feature rather than a top-k slice, so
baseline and scenario explanations can be compared feature by feature. The
strategy engine is still given the usual top-10 slice, keeping candidate scores
consistent with the Step 4 recommendation service.

---

## 5. Scenario catalogue

Scenarios are data (`agent/simulation/catalogue.py`), each tied to a Step 4
strategy. Neither a caller nor the LLM can invent one.

| Scenario | Change | Strategy | Applies when |
|---|---|---|---|
| `annual_contract` | `Contract → One year` | `CONTRACT_CONVERSION` | currently month-to-month |
| `two_year_contract` | `Contract → Two year` | `CONTRACT_CONVERSION` | currently month-to-month or one year |
| `tech_support_addon` | `TechSupport → Yes` | `SUPPORT_INTERVENTION` | currently `No` |
| `online_security_addon` | `OnlineSecurity → Yes` | `SUPPORT_INTERVENTION` | currently `No` |
| `security_and_backup_bundle` | `OnlineSecurity → Yes`, `OnlineBackup → Yes` | `SERVICE_BUNDLE_OPTIMIZATION` | both currently `No` |
| `automatic_payment_method` | `PaymentMethod → Bank transfer (automatic)` | `PRICING_VALUE` | currently electronic or mailed check |
| `annual_contract_with_support` | `Contract → One year`, `TechSupport → Yes` | `CONTRACT_CONVERSION` | both preconditions hold |

Three deliberate omissions:

- **No scenario changes `tenure`.** Tenure records how long the customer has
  been with the operator. It is a historical fact, and no intervention can make
  a customer have joined earlier. Simulating it would be meaningless.
- **No scenario changes `MonthlyCharges` or `TotalCharges`.** A price change is
  technically simulatable, but only with an amount the business supplies.
  Inventing one would fabricate an offer, which the Step 4 guardrails exist to
  prevent. Callers with a real approved figure use `build_custom_scenario()`,
  which goes through identical validation.
- **No scenario represents human activity.** See section 11.

**The add-on caveat.** Enabling a service add-on holds `MonthlyCharges`
constant. If the add-on carries a fee, a realistic profile would also show
higher charges, which the model treats as a separate risk driver. Every add-on
scenario states this in its own `limitations`; it is an assumption, not an
oversight.

---

## 6. Feature validation

Three checks run before anything reaches the model.

**Value validity.** The domain is read from the *fitted* preprocessor's
`OneHotEncoder.categories_` (via the Step 3 feature map), never hardcoded.
`Contract = "12 months"` is rejected because the encoder never learned it — and
because `handle_unknown="ignore"` would otherwise encode it as all-zeros and
return a confident-looking prediction for a profile that means nothing. Numeric
features must be finite numbers; `tenure`, `MonthlyCharges`, and `TotalCharges`
cannot be negative, and `SeniorCitizen` must be 0 or 1.

**Applicability.** A scenario is skipped when the customer's current values are
outside its precondition, or when it would change nothing.

**Structural consistency.** The Telco data encodes dependencies, verified across
all 7,043 rows without exception:

| Rule | Verified |
|---|---|
| `InternetService = "No"` ⟹ all six internet add-ons are `"No internet service"` | 1,526 / 1,526 rows |
| `InternetService ≠ "No"` ⟹ add-ons are `"Yes"` or `"No"` | 5,517 / 5,517 rows |
| `PhoneService = "No"` ⟹ `MultipleLines = "No phone service"` | 682 / 682 rows |
| `PhoneService = "Yes"` ⟹ `MultipleLines` is `"Yes"` or `"No"` | 6,361 / 6,361 rows |

The check runs on the profile *after* the change, because a change is only
contradictory in combination with the rest of the profile. Enabling
`TechSupport` for a customer with no internet describes a customer who cannot
exist, so it is rejected rather than predicted.

An invalid scenario is reported in `rejected_scenarios` and the comparison
continues — one bad scenario never costs the reviewer the other results.

---

## 7. SHAP comparison

For both the baseline and each scenario the **real** Step 3 explainer runs, and
the results are paired feature by feature into `DriverDelta` records sorted by
how far each contribution moved. This is the part that turns "the number changed"
into "here is what changed it":

```
feature              baseline   scenario     change
Contract              +0.4077    -1.0255    -1.4332 *
tenure                +1.3752    +1.3752    +0.0000
MonthlyCharges        +0.7998    +0.7998    +0.0000
(* = feature changed by the scenario)
```

Because the model is linear, untouched features keep exactly their baseline
contribution, which makes the movement unambiguous. Scenario explanations
satisfy the same additivity property as baseline ones —
`base_value + Σ SHAP = model log-odds` — and there is a test asserting it.

---

## 8. Scenario ranking

"Pick the lowest probability" is a bad rule: it would happily recommend flipping
a feature that is currently *protecting* the customer, purely because the linear
score moves. The score is therefore:

```
ranking_score = 0.50 × model_response
              + 0.30 × evidence_alignment
              + 0.20 × driver_targeting

if the scenario conflicts with the evidence:
    ranking_score × = 0.50
```

| Factor | Definition |
|---|---|
| `model_response` | `max(0, baseline − scenario) / baseline`. A scenario that raises the estimate scores zero rather than negative. |
| `evidence_alignment` | The Step 4 strategy engine's alignment score for this scenario's strategy — the share of the customer's risk-increasing SHAP impact that strategy addresses. Zero when the strategy is not an eligible candidate, which keeps contraindicated plays out of the ranking. |
| `driver_targeting` | The share of risk-increasing SHAP impact carried by the features the scenario actually changes. |

**Conflict penalty.** A scenario "conflicts with the evidence" when it changes a
feature that currently *lowers* this customer's risk estimate. The score is
halved and the reason recorded.

The weights are a stance, not a tuning result: the model's response matters most,
but on its own it can never exceed 0.50, so it cannot outrank a scenario that is
both responsive and evidence-aligned. Every factor is reported on the outcome so
a reviewer can recompute the score by hand.

**Selection.** A scenario is recommended only if the model's estimate actually
falls under it *and* it does not conflict with the evidence. When nothing
qualifies, `recommended_scenario_id` is `null` and the reason says so — the
least-bad option is not put forward as a recommendation.

---

## 9. AI interpretation

By the time the AI runs, every scenario has been simulated, scored, and ranked.
The division of labour from Step 4 is unchanged:

> **The system owns the facts. The AI provides the reasoning.**

The model receives the finished results and returns prose: what they show,
whether they line up with the customer's strongest risk drivers, and what the
reviewer should check. It cannot change a probability, a SHAP value, a ranking
score, or the recommendation. If it reads a different scenario as most promising,
that disagreement is recorded in `ai_alternative_scenario_id` for the human to
weigh — it never overwrites the ranking.

Every failure — no provider, timeout, invalid JSON, a scenario that was never
simulated, causal language — falls back to a deterministic interpretation
written from the system's own ranking, labelled
`provider = "deterministic_fallback"` with an explicit `fallback_reason`.

---

## 10. Output contract

`WhatIfResult` (`agent/models/whatif.py`):

```json
{
  "customer_id": "7590-VHVEG",
  "baseline": { "churn_probability": 0.8064, "risk_level": "HIGH", "prediction": 1,
                "model_version": "1.0.0", "top_drivers": [ ... ] },
  "candidate_strategy_ids": ["EARLY_LIFECYCLE_ONBOARDING", "PRICING_VALUE", "..."],
  "scenarios": [
    {
      "scenario_id": "two_year_contract",
      "strategy_id": "CONTRACT_CONVERSION",
      "changed_features": { "Contract": "Two year" },
      "scenario_probability": 0.4984,
      "absolute_probability_change": -0.308,
      "percentage_point_change": -30.8,
      "baseline_risk_level": "HIGH",
      "scenario_risk_level": "MEDIUM",
      "risk_level_changed": true,
      "baseline_top_drivers": [ ... ],
      "scenario_top_drivers": [ ... ],
      "driver_deltas": [ ... ],
      "ranking_score": 0.232,
      "ranking_factors": { "model_response": 0.3819, "evidence_alignment": 0.0821,
                           "driver_targeting": 0.0821, "conflict_penalty_applied": false },
      "conflicts_with_evidence": false,
      "model_based_interpretation": "Under the 'Move to Two-Year Contract' profile the trained model estimates a lower churn probability: 80.64% to 49.84% (-30.80 percentage points). ...",
      "limitations": [ "Model-based what-if estimate — not a causal prediction.", "..." ]
    }
  ],
  "rejected_scenarios": [ { "scenario_id": "...", "reason": "..." } ],
  "unsimulatable_interventions": [ { "strategy_id": "...", "intervention": "...",
                                     "reason": "...", "simulatable": false } ],
  "recommended_scenario_id": "two_year_contract",
  "selection_reason": "...",
  "ranking_methodology": "...",
  "ai_interpretation": "...",
  "ai_considerations": [ "..." ],
  "ai_alternative_scenario_id": null,
  "provider": "deterministic_fallback",
  "limitations": [ "..." ],
  "requires_human_approval": true
}
```

`requires_human_approval` is enforced by a validator that rejects `False`.

### Safety boundary

The simulator changes nothing. It sends no message, alters no account or
subscription, issues no discount, calls no CRM, and writes to no database. It
reads a customer record, evaluates hypothetical copies of it in memory, and
returns a result object.

---

## 11. Interventions that cannot be simulated

The most important honest answer this layer gives is "no estimate exists".

| Strategy | Intervention | Why not |
|---|---|---|
| `SUPPORT_INTERVENTION` | Proactive service review call, priority support handling | No feature represents support quality, response time, or human outreach — only subscription to the TechSupport and OnlineSecurity products |
| `EARLY_LIFECYCLE_ONBOARDING` | Onboarding help, service education, proactive check-in | No feature represents onboarding; the related feature, `tenure`, is a historical fact |
| `PRICING_VALUE` | Targeted discount or retention offer | `MonthlyCharges` exists, but simulating it needs a business-supplied amount; inventing one would fabricate an offer |
| `GENERAL_RETENTION_REVIEW` | Escalation to a specialist | An internal process that changes nothing about the customer's profile |

These are returned in `unsimulatable_interventions` with
`"simulatable": false`. A UI can then show "AI recommendation available;
what-if simulation unavailable for this intervention" instead of a fabricated
number.

This matters most for customer `7590-VHVEG`, whose single largest risk driver is
short tenure — and *no scenario can address it*. The system says so rather than
substituting a scenario that happens to move the score.

---

## 12. Limitations

- **Not causal.** The central limitation, restated on every result.
- **Association, not mechanism.** The model learned that two-year customers churn
  less. Those customers also chose two-year contracts, and that self-selection is
  baked into the coefficient.
- **Off-distribution profiles.** A hypothetical profile may be one that rarely or
  never occurs in the training data; the model will still return a confident
  number.
- **Add-ons hold price constant.** Documented per scenario in section 5.
- **Coupled features are moved independently.** A real contract change might
  arrive with a price change; the simulator changes only what the scenario names.
- **The catalogue is illustrative.** Real deployment needs the operator's actual
  approved offers and eligibility rules.
- **Model-specific.** All of this describes the Step 2 logistic regression. Retrain
  the model and every number here changes.
- **No effect size.** The simulator cannot tell you how many customers would
  actually stay. Only a controlled experiment can.

---

## 13. Worked example — customer 7590-VHVEG

Real output from `python -m agent.whatif_cli --customer-id 7590-VHVEG`
(deterministic interpretation, no LLM configured):

```
BASELINE  80.64% HIGH
  tenure            value=1               shap=+1.3752  increases_risk
  MonthlyCharges    value=29.85           shap=+0.7998  increases_risk
  InternetService   value=DSL             shap=-0.6895  decreases_risk
  TotalCharges      value=29.85           shap=-0.4549  decreases_risk
  Contract          value=Month-to-month  shap=+0.4077  increases_risk

  rank  scenario                           estimate    change   score
  1     two_year_contract                   49.84%   -30.80pp  0.2320
  2     annual_contract_with_support        61.10%   -19.54pp  0.1681
  3     annual_contract                     66.75%   -13.89pp  0.1272
  4     automatic_payment_method            73.59%    -7.05pp  0.1170
  5     online_security_addon               75.29%    -5.35pp  0.0593
  6     tech_support_addon                  76.52%    -4.12pp  0.0507

  not applicable: security_and_backup_bundle (customer already has OnlineBackup)

RECOMMENDED: two_year_contract     RISK: HIGH → MEDIUM     APPROVAL REQUIRED: True
```

Two details worth noticing.

**The ranking is not the probability ordering by accident.** `two_year_contract`
wins on `model_response` (0.38), but `automatic_payment_method` ranks fourth
despite a modest 7-point drop because it has the *highest* evidence alignment
(0.21) of any scenario — its strategy addresses more of the customer's actual
SHAP evidence than the contract plays do. Change the weights and that ordering
changes; that is exactly why the factors are published on every outcome.

**The biggest driver is untouchable.** Short tenure contributes +1.3752, more
than three times the contract contribution, and no scenario can change it. The
honest reading is that the model's estimate is dominated by a fact about this
customer that no intervention addresses, and the contract scenarios work on the
second-tier drivers. A simulator that hid that would be worse than no simulator.

---

## 14. Usage

```bash
# Readable report
python -m agent.whatif_cli --customer-id 7590-VHVEG

# JSON for downstream consumers
python -m agent.whatif_cli --customer-id 7590-VHVEG --json-output

# Force the deterministic interpretation even when an LLM is configured
python -m agent.whatif_cli --customer-id 7590-VHVEG --no-llm
```

```python
from agent.services.whatif_service import run_whatif_analysis
from agent.providers.llm_provider import build_provider

result = run_whatif_analysis(customer_record, provider=build_provider())
result.recommended_scenario_id
result.requires_human_approval          # always True
```

Deterministic simulation without the AI layer:

```python
from agent.simulation.comparison import compare_retention_scenarios

result = compare_retention_scenarios(customer_record)
```

---

## 15. Testing

`agent/tests/` — the what-if layer adds 106 tests, none of which call a paid API.

| File | Kind | Covers |
|---|---|---|
| `test_scenario_catalogue.py` | deterministic | catalogue integrity, strategy links, unsimulatable registry, no invented discounts |
| `test_scenario_validation.py` | deterministic | feature domain, invalid categories and types, applicability, impossible combinations |
| `test_ranking.py` | deterministic | each factor, the conflict penalty, score reproducibility, selection rules |
| `test_scenario_interpretation.py` | mocked provider | prompt content, every fallback path, AI cannot alter facts, causal language rejected |
| `test_whatif_simulation.py` | integration | real model and SHAP for `7590-VHVEG`, no retraining, additivity, risk bands |

The integration file skips itself when the artifacts are absent, and it asserts
that the fast unit-test feature-domain fixture still matches the real fitted
preprocessor — so the unit tests cannot silently drift from the model.
