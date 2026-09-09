# AI Retention Intelligence Layer

The agent layer turns a churn prediction into a *decision*: which retention play
a human specialist should consider for this customer, why, and how much the
system trusts that suggestion.

It is deliberately **not** "send the customer record to an LLM and print the
reply". The language model never sees a free-form question, never chooses what
counts as evidence, and never produces a number that reaches the user.

---

## 1. Where the agent sits

```
Customer Profile
       ↓
Churn Prediction            (ml/src/prediction/predictor.py — Step 2)
       ↓
SHAP Evidence               (ml/src/explainability/explainer.py — Step 3)
       ↓
Risk Interpretation         (agent/models/evidence.py)
       ↓
Retention Strategy Engine   (agent/strategies/evaluator.py)
       ↓
Candidate Strategies
       ↓
AI Reasoning Layer          (agent/services/reasoning_service.py)
       ↓
Personalized Recommendation (agent/services/recommendation_service.py)
       ↓
Human Approval Required
```

Each arrow is a typed contract. `CustomerEvidence` is built directly from
`explain_customer()` output, so a change to the SHAP contract fails loudly in one
place rather than quietly degrading recommendations.

---

## 2. The division of labour

This is the single most important design decision in the layer:

| Produced by | What |
|---|---|
| **ML model** | churn probability, predicted class, risk band, model version |
| **SHAP** | which features moved the prediction, by how much, in which direction |
| **Strategy engine** | which retention plays are eligible and how well each matches the evidence |
| **Confidence model** | how much to trust the recommendation |
| **Catalogue** | the objective and allowed actions of the chosen play |
| **LLM** | *the wording only* — the recommendation sentence and reasoning bullets |

The LLM writes prose; the system owns every fact. Even if the model hallucinates
a probability, a SHAP value, or an objective in its reply, those fields are
discarded — the recommendation is assembled from the evidence objects, not from
the model's JSON.

---

## 3. Retention strategy catalogue

Defined as data in `agent/strategies/catalogue.py`. The LLM may only select from
the candidates the engine hands it; anything else is rejected.

| Strategy | Applicable risk drivers | Objective |
|---|---|---|
| `CONTRACT_CONVERSION` | `Contract` | Increase commitment and address contract-related risk |
| `PRICING_VALUE` | `MonthlyCharges`, `TotalCharges`, `PaperlessBilling`, `PaymentMethod` | Improve perceived value without assuming a discount |
| `SUPPORT_INTERVENTION` | `TechSupport`, `OnlineSecurity` | Resolve service friction |
| `SERVICE_BUNDLE_OPTIMIZATION` | `InternetService`, `StreamingTV`, `StreamingMovies`, `OnlineBackup`, `DeviceProtection`, `MultipleLines`, `PhoneService` | Improve service fit |
| `EARLY_LIFECYCLE_ONBOARDING` | `tenure` | Improve early engagement (first 12 months) |
| `GENERAL_RETENTION_REVIEW` | — (fallback) | Escalate to a retention specialist |

Every entry carries `description`, `objective`, `allowed_actions`,
`contraindications`, and `priority`. Two eligibility guards are expressed as
data rather than code so they stay auditable:

- `excluded_profile_values` — e.g. `CONTRACT_CONVERSION` is ruled out when
  `Contract == "Two year"`. The system must never propose converting a customer
  who already holds the longest contract.
- `max_tenure_months` — e.g. `EARLY_LIFECYCLE_ONBOARDING` applies only within the
  first 12 months. If `tenure` is missing, the strategy is refused rather than
  guessed at.

---

## 4. How strategies are scored

For each eligible strategy:

```
matched_drivers  = risk-increasing SHAP drivers whose feature is in
                   strategy.applicable_risk_drivers
alignment_score  = Σ impact(matched_drivers)
```

`impact` is each driver's share of the customer's total absolute SHAP
contribution (produced in Step 3), so a score of `0.28` reads as *"this strategy
targets 28% of what moved the model's prediction"*.

Three deliberate choices:

1. **Only risk-increasing drivers count.** A feature currently lowering the
   customer's risk is not a problem to intervene on. This is why a customer whose
   `InternetService` is *protective* gets no bundle-optimisation candidate.
2. **Business priority is a tie-break only.** Ranking is by evidence first
   (`-alignment_score`, then `priority`, then id). Preference never overrides
   evidence.
3. **The escalation play is always a candidate.** There is always something valid
   to return, and the human reviewer always sees "escalate" as an option.

The engine never contains rules like `if churn > 0.7: offer_discount()`. Such a
rule discards the explanation, which is precisely the information that makes the
recommendation defensible.

---

## 5. AI reasoning layer

`ReasoningService` builds a JSON payload containing the customer profile, the
prediction, the SHAP drivers, and the candidate strategies with their allowed
actions and contraindications. The system prompt
(`agent/prompts/retention_prompt.py`) requires the model to:

- use only the supplied information and invent no customer facts;
- invent no prices, discounts, percentages, free items, or fee waivers;
- guarantee no outcome;
- treat SHAP as model evidence, never as causation;
- select exactly one strategy from the supplied candidates;
- respect each strategy's allowed actions and contraindications;
- claim no executed action;
- return a single JSON object.

The reply is then **validated, not trusted**:

| Check | Failure behaviour |
|---|---|
| Parses as a JSON object (code fences tolerated) | fallback |
| `strategy_id` is among the *candidates offered* | fallback |
| `recommendation` present and under 1200 characters | fallback |
| `reasoning` contains at least one usable bullet (capped at 6) | fallback |
| Prose passes the safety guardrails | fallback |

Note that the strategy is validated against the candidates, not the whole
catalogue: a real-but-ineligible play (contract conversion for a two-year
customer) is rejected exactly like an invented one.

---

## 6. Safety guardrails

`agent/guardrails.py` scans every piece of model-written prose for patterns that
map to a concrete business risk:

| Rule | Catches |
|---|---|
| `fabricated_currency_amount` | `$20 off`, `500 rupees` |
| `fabricated_percentage_offer` | `25% discount` — but **not** `35% of total SHAP impact` |
| `fabricated_free_offer` | `free month`, `waive the fee` |
| `outcome_guarantee` | `guarantees they stay`, `will prevent churn` |
| `causal_claim` | `the contract causes churn` |
| `claimed_executed_action` | `I have emailed the customer`, `a discount has been applied` |

The percentage rule is context-sensitive: a percentage only counts as a violation
when offer language (`discount`, `off`, `credit`, `waive`, `free`, …) appears
within 60 characters. Quoting SHAP impact as a percentage is legitimate and must
not trigger a needless fallback.

A prompt is a request, not a constraint — these checks verify the model obeyed.

---

## 7. Fallback behaviour

Every failure mode resolves to the deterministic engine, which writes the
recommendation from the catalogue and the real evidence:

| Situation | `provider` | `fallback_reason` |
|---|---|---|
| No `LLM_PROVIDER` configured | `deterministic_fallback` | "No LLM provider is configured…" |
| API key or endpoint missing | `deterministic_fallback` | "The LLM provider is not usable…" |
| Timeout | `deterministic_fallback` | `LLMTimeoutError: …` |
| Network / HTTP error | `deterministic_fallback` | `LLMUnavailableError: …` |
| Invalid JSON | `deterministic_fallback` | `LLMResponseError: …` |
| Strategy not among candidates | `deterministic_fallback` | "…not among the candidates offered…" |
| Guardrail violation | `deterministic_fallback` | "…rejected by a safety guardrail…" |
| Unexpected provider bug | `deterministic_fallback` | `Unexpected LLM error: …` |

The agent never raises an LLM error at its caller, and it never pretends an LLM
wrote something it did not: the `provider` field, the `fallback_reason`, and an
extra entry in `limitations` all state the truth.

Deterministic prose is assembled only from values present in the evidence, so
this path also cannot state a customer fact that was not supplied.

---

## 8. Confidence

Confidence is computed by the system (`agent/confidence.py`), never claimed by
the model. Four measurable factors:

| Factor | Weight | Meaning |
|---|---|---|
| `prediction_decisiveness` | 0.30 | Distance of the churn probability from the 0.5 boundary, saturating at ±0.35 |
| `evidence_alignment` | 0.30 | Share of total SHAP movement the chosen strategy addresses |
| `actionable_support` | 0.20 | Number of matched risk-increasing drivers (2+ = full support) |
| `discrimination` | 0.20 | Margin over the best alternative, relative to the chosen score |

Bands: `≥ 0.65 → HIGH`, `≥ 0.40 → MEDIUM`, otherwise `LOW`.

Hard caps, applied after the arithmetic:

- the escalation fallback is always `LOW`;
- no risk-increasing drivers means `LOW`;
- a customer in the `LOW` risk band is capped at `MEDIUM`.

If the AI selects a lower-ranked strategy than the engine's top choice, the
margin collapses to zero and confidence drops accordingly — overriding the
evidence ranking is allowed, but it costs trust.

Finally, `downgrade_only()` lets the LLM's own claim **lower** confidence but
never raise it. A model asserting "HIGH" is ignored; a model flagging uncertainty
is respected.

---

## 9. Output contract

`agent/models/recommendation.py` — `RetentionRecommendation`:

```json
{
  "customer_id": "7590-VHVEG",
  "churn_probability": 0.8064,
  "risk_level": "HIGH",
  "model_version": "1.0.0",
  "selected_strategy": {
    "strategy_id": "EARLY_LIFECYCLE_ONBOARDING",
    "strategy_name": "Early Lifecycle Onboarding"
  },
  "recommendation": "...",
  "reasoning": ["..."],
  "supporting_evidence": [
    {"feature": "tenure", "value": 1, "shap_value": 1.3752, "direction": "increases_risk"}
  ],
  "objective": "Improve early customer engagement during the highest-risk period of the lifecycle.",
  "confidence": "MEDIUM",
  "confidence_rationale": "Weighted confidence score 0.49 from ...",
  "requires_human_approval": true,
  "limitations": ["..."],
  "provider": "deterministic_fallback",
  "fallback_reason": "No LLM provider is configured; used the deterministic strategy engine.",
  "candidate_strategy_ids": ["EARLY_LIFECYCLE_ONBOARDING", "PRICING_VALUE", "..."],
  "generated_at": "2026-09-07T00:00:00Z"
}
```

`requires_human_approval` is enforced by a Pydantic validator that rejects
`False`. No code path — including a compromised LLM reply — can produce an
auto-approved recommendation.

`to_api_contract()` projects this onto the `RecommendationResponse` schema
defined in Step 1, so the future endpoint needs no translation logic of its own.

### Safety boundary

The agent has no ability to act. It cannot send email or SMS, change an account,
alter pricing, issue a discount, call a CRM, or execute a transaction. It returns
a recommendation object and nothing else.

---

## 10. Provider abstraction

`LLMProvider` (`agent/providers/base.py`) declares `is_available()` and
`complete(system_prompt, user_prompt)`. Implementations must translate their own
errors into `LLMTimeoutError`, `LLMUnavailableError`, or `LLMResponseError` so
callers handle failures uniformly.

`OpenAICompatibleProvider` covers OpenAI, OpenRouter, Groq, Ollama, vLLM, LM
Studio, and any other `/chat/completions` endpoint. Selecting a backend is
configuration, not code:

```bash
LLM_PROVIDER=openai_compatible
LLM_API_KEY=...            # environment only, backend only, never logged
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

`build_provider()` returns `None` when the LLM is unconfigured, which is a
supported production mode rather than an error state.

---

## 11. Worked example — customer 7590-VHVEG

Real output from the saved Step 2 model and Step 3 explainer, deterministic path
(`python -m agent.cli --customer-id 7590-VHVEG`):

```
Churn probability : 0.8064   Risk level: HIGH

TOP SHAP DRIVERS
  tenure            value=1               shap=+1.3752  impact=27.68%  increases_risk
  MonthlyCharges    value=29.85           shap=+0.7998  impact=16.10%  increases_risk
  InternetService   value=DSL             shap=-0.6895  impact=13.88%  decreases_risk
  TotalCharges      value=29.85           shap=-0.4549  impact= 9.15%  decreases_risk
  Contract          value=Month-to-month  shap=+0.4077  impact= 8.21%  increases_risk

CANDIDATE STRATEGIES
  1. EARLY_LIFECYCLE_ONBOARDING   0.2768   tenure
  2. PRICING_VALUE                0.2109   MonthlyCharges, PaymentMethod
  3. CONTRACT_CONVERSION          0.0821   Contract
  4. SUPPORT_INTERVENTION         0.0641   OnlineSecurity, TechSupport
  5. GENERAL_RETENTION_REVIEW     0.0000   escalation path
  Not eligible: SERVICE_BUNDLE_OPTIMIZATION (no matching risk-increasing driver)

SELECTED: EARLY_LIFECYCLE_ONBOARDING     CONFIDENCE: MEDIUM     APPROVAL REQUIRED: True
```

Worth noting what the system did *not* do. The obvious hackathon heuristic —
"high risk, month-to-month, therefore offer a contract discount" — ranks fourth
here. The model's actual evidence says this customer's risk is dominated by being
one month into the relationship, so onboarding outranks contract conversion by
more than 3×. That difference is the point of the layer.

---

## 12. Testing

`agent/tests/` — 124 tests, none of which call a paid API.

| File | Kind | Covers |
|---|---|---|
| `test_catalogue.py` | deterministic | catalogue integrity, required fields, immutability |
| `test_evaluator.py` | deterministic | scoring, ranking, eligibility guards, invalid evidence |
| `test_confidence.py` | deterministic | factor behaviour, hard caps, downgrade-only rule |
| `test_guardrails.py` | deterministic | each safety rule, plus legitimate percentages |
| `test_providers.py` | mocked transport | availability, error translation, key never leaked, factory |
| `test_reasoning_service.py` | mocked provider | prompt content, parsing, every rejection path |
| `test_recommendation_service.py` | mocked provider | all eight fallback paths, schema invariants, confidence ownership |
| `test_integration_pipeline.py` | integration | real model + real SHAP for `7590-VHVEG` |

The integration file skips itself when the model artifacts or dataset are absent,
so a fresh clone can still run the rest of the suite.

---

## 13. Known limitations

- **SHAP is not causal.** Every recommendation restates this. Acting on the
  strongest driver is a heuristic, not a proven intervention.
- **The strategy catalogue is illustrative.** Real deployment needs the
  operator's actual approved plays, eligibility rules, and offer inventory.
- **No effect estimation.** The system does not predict how much a strategy would
  reduce churn risk. That is the what-if simulator, deliberately deferred.
- **Driver-to-strategy mapping is hand-authored.** It encodes analyst judgement
  about which features are actionable, and should be reviewed with the business.
- **Confidence is not calibrated against outcomes.** It measures evidence
  quality, not observed retention success; calibration needs intervention data
  the project does not have.
- **Guardrails are pattern-based.** They catch the obvious failure classes, not
  every possible fabrication. They are a safety net beneath human approval, not a
  replacement for it.

---

## 14. Not built yet (by design)

FastAPI endpoints, database persistence of recommendations and approvals, the
dashboard, and the what-if retention simulator. The planned sequence is:

```
Prediction → SHAP → Agent → What-if scenarios → Strategy comparison → Human approval
```
