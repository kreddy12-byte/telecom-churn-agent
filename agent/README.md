# AI Retention Agent Module

Evidence-grounded retention recommendations. The agent consumes ML predictions
and SHAP explanations, evaluates them against a controlled catalogue of
retention strategies, and returns a structured recommendation that always
requires human approval.

It also hosts the **what-if simulator** (`agent/simulation/`), which evaluates
how the existing trained model responds to hypothetical customer profiles. It
retrains nothing and claims no causal effect.

All LLM calls happen here, inside the backend process. Keys come from
environment variables and are never exposed to the frontend.

Full design rationale: [docs/AGENT.md](../docs/AGENT.md) and
[docs/WHAT_IF_SIMULATOR.md](../docs/WHAT_IF_SIMULATOR.md).

---

## Structure

| Path | Purpose |
|---|---|
| `models/evidence.py` | `CustomerEvidence` — the typed contract from ML/SHAP |
| `models/strategy.py` | `RetentionStrategy`, `StrategyCandidate`, `StrategyEvaluation` |
| `models/recommendation.py` | `RetentionRecommendation` — the output contract |
| `strategies/catalogue.py` | The six approved retention plays, defined as data |
| `strategies/evaluator.py` | Scores strategies against real SHAP evidence |
| `confidence.py` | Deterministic confidence model |
| `guardrails.py` | Safety checks applied to LLM-written prose |
| `prompts/retention_prompt.py` | System prompt and structured evidence payload |
| `providers/base.py` | `LLMProvider` abstraction and shared error types |
| `providers/llm_provider.py` | OpenAI-compatible client + factory |
| `services/reasoning_service.py` | Calls the LLM, validates and rejects its output |
| `services/recommendation_service.py` | Orchestration and deterministic fallback |
| `services/evidence_builder.py` | Bridge from `explain_customer()` to evidence |
| `cli.py` | `python -m agent.cli` — readable end-to-end report |

### What-if simulator (Step 5)

| Path | Purpose |
|---|---|
| `models/scenario.py` | `Scenario`, `UnsimulatableIntervention` |
| `models/whatif.py` | `WhatIfResult`, `ScenarioOutcome`, SHAP snapshots and deltas |
| `simulation/feature_domain.py` | Valid feature values, read from the fitted preprocessor |
| `simulation/catalogue.py` | Approved scenarios + interventions the model cannot represent |
| `simulation/validator.py` | Feature, applicability, and structural-consistency checks |
| `simulation/simulator.py` | Baseline and scenario prediction with real SHAP |
| `simulation/ranking.py` | The published scoring formula |
| `simulation/comparison.py` | `compare_retention_scenarios()` |
| `simulation/report.py` | Human-readable rendering |
| `services/scenario_interpretation_service.py` | AI interpretation + deterministic fallback |
| `services/whatif_service.py` | End-to-end orchestration |
| `whatif_cli.py` | `python -m agent.whatif_cli` |

---

## Usage

### From code

```python
from agent.providers.llm_provider import build_provider
from agent.services.evidence_builder import build_customer_evidence
from agent.services.recommendation_service import RecommendationService

evidence = build_customer_evidence(customer_record)          # prediction + SHAP
service = RecommendationService(provider=build_provider())   # None → deterministic
recommendation = service.recommend(evidence)

recommendation.requires_human_approval   # always True
recommendation.to_api_contract()         # Step 1 RecommendationResponse shape
```

### From the command line

```bash
python -m agent.cli --customer-id 7590-VHVEG        # readable report
python -m agent.cli --customer-id 7590-VHVEG --json-output
python -m agent.cli --customer-id 7590-VHVEG --no-llm   # force deterministic
```

### What-if simulation

```python
from agent.services.whatif_service import run_whatif_analysis
from agent.simulation.comparison import compare_retention_scenarios

result = run_whatif_analysis(customer_record, provider=build_provider())
deterministic_only = compare_retention_scenarios(customer_record)
```

```bash
python -m agent.whatif_cli --customer-id 7590-VHVEG
python -m agent.whatif_cli --customer-id 7590-VHVEG --json-output
python -m agent.whatif_cli --customer-id 7590-VHVEG --no-llm
```

---

## Configuration

Set in `backend/.env` (see `backend/.env.example`):

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `none` | `none` or `openai_compatible` |
| `LLM_API_KEY` | – | Credentials; backend only, never logged |
| `LLM_API_BASE_URL` | – | e.g. `https://api.openai.com/v1` |
| `LLM_MODEL` | – | Model id |
| `LLM_TEMPERATURE` | `0.2` | Low: this is decision support, not creative writing |
| `LLM_MAX_OUTPUT_TOKENS` | `700` | Response cap |
| `LLM_TIMEOUT_SECONDS` | `20` | After this, the deterministic engine takes over |
| `AGENT_EVIDENCE_DRIVER_COUNT` | `10` | SHAP drivers the strategy engine evaluates |

With no LLM configured the agent still produces complete recommendations from
its deterministic strategy engine, clearly labelled
`provider = "deterministic_fallback"`.

---

## Guarantees

1. `requires_human_approval` is always `true` — enforced by a schema validator.
2. The agent executes no real-world action of any kind. The simulator changes
   nothing: it evaluates hypothetical copies of a customer record in memory.
3. Probabilities, SHAP values, scenario rankings, objectives, and confidence are
   computed by the system; the LLM only supplies wording.
4. Strategies and scenarios come exclusively from their catalogues, filtered to
   those eligible for the customer.
5. Any LLM failure or rule violation degrades to the deterministic engine, and
   the output says so.
6. Simulation results are model-based what-if estimates, never causal claims;
   interventions with no representing feature are marked `simulatable: false`
   instead of being given a number.

---

## Tests

```bash
python -m pytest agent/tests -q
```

230 tests. LLM behaviour is covered with mocked providers; no test makes a paid
API call. The integration tests use the real saved model and skip themselves
when the artifacts are absent — and they assert that the fast synthetic
feature-domain fixture still matches the real fitted preprocessor, so the unit
tests cannot drift away from the model.
