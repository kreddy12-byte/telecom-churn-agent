# System Architecture

## Overview

The Telecom Churn Agent is a modular full-stack application. The **FastAPI backend is the sole integration layer**. The React frontend never talks to the database, ML artifacts, or LLM APIs directly.

```
Frontend (React / Vite)
        │  HTTP (Axios)
        ▼
FastAPI Backend
        │
   ┌────┴────┬─────────────┬──────────────┐
   ▼         ▼             ▼              ▼
ML Service  Explanation  AI Agent      Database
(predict)   (SHAP)       (LLM recs)   (PostgreSQL)
```

This is intentionally a **modular monolith**, not a set of microservices.

---

## Module responsibilities

### `frontend/`

Reviewer-facing decision-support UI (React / Vite / Tailwind):

| Area | Responsibility |
|------|----------------|
| `src/pages/` | Overview, Customers, Customer Intelligence, Actions, Model information |
| `src/components/` | Layout shell, risk badges, SHAP bars, what-if comparison, decision dialogs |
| `src/services/api.js` | Sole HTTP client. Calls FastAPI only — never an LLM provider |
| `src/hooks/` | Customer-intelligence orchestration (predict → explain → recommend → simulate) |

The product story on the customer page is: **risk → why (SHAP) → recommendation → what-if → human decision**.

No secrets. Public env is `VITE_API_BASE_URL` plus Auth0 SPA values
(`VITE_AUTH0_DOMAIN`, `VITE_AUTH0_CLIENT_ID`, `VITE_AUTH0_AUDIENCE`). Client
secrets never belong on the frontend. Auth setup: [AUTHENTICATION.md](AUTHENTICATION.md).

### `backend/`

Central API and orchestration:

| Package | Responsibility |
|---------|----------------|
| `app/api/routes/` | Thin HTTP handlers; validation via Pydantic schemas |
| `app/api/exception_handlers.py` | Uniform error envelope; no secrets in responses |
| `app/core/` | Config (env vars), logging, shared dependencies |
| `app/schemas/` | Request/response contracts |
| `app/services/` | Orchestration only — prediction, explanation, recommendation, what-if, actions |
| `app/db/` | Engine, ORM models, repositories, seed |

**Rule:** routes → services → repositories. Business logic does not live in route files; SQL does not live in services. ML probabilities, SHAP values, strategy scores, and what-if rankings are never recomputed in the backend — the services call the existing `ml/` and `agent/` entry points.

API surface: [API.md](API.md).

### `ml/`

Offline and online ML assets:

- Preprocessing, training, prediction helpers, SHAP explainability.
- Artifacts stored under `ml/models/`.
- Invoked by backend services — no public HTTP surface.

### `agent/`

Retention recommendation agent:

- Controlled strategy catalogue, evidence-based strategy engine, LLM reasoning
  layer, safety guardrails, deterministic fallback, and confidence model.
- Consumes ML prediction + SHAP evidence; the LLM supplies wording only, and all
  facts and confidence are computed by the system.
- API keys loaded only via backend environment variables.
- Output matches the shared recommendation contract via
  `RetentionRecommendation.to_api_contract()`; `requires_human_approval` is
  always true and the agent executes no real-world action.
- Design detail: [AGENT.md](AGENT.md).

### `agent/simulation/`

What-if retention simulator and strategy comparison engine:

- Evaluates how the **existing** trained model responds to hypothetical
  customer-profile scenarios. No retraining, no second prediction pipeline, no
  additional model artifact — it calls the same `explain_customer()` entry point
  as the rest of the system.
- Scenarios come from a controlled catalogue tied to the strategy catalogue, and
  are validated against a feature domain read from the *fitted* preprocessor, so
  an invalid category or an impossible service combination is rejected rather
  than silently encoded as all-zeros.
- Runs the real SHAP explainer for the baseline and every scenario, pairing them
  into per-feature deltas so a reviewer can see *why* the estimate moved.
- Ranks scenarios with a published formula combining model response, strategy
  evidence alignment, and driver targeting — deliberately not "lowest
  probability wins".
- Interventions with no representing feature (a support call, onboarding help, a
  discount with no business-supplied amount) are returned as
  `simulatable: false` rather than given a fabricated number.
- Results are **model-based what-if estimates, not causal predictions**; the
  `causal_effect_claim` guardrail rejects LLM prose that says otherwise.
- Design detail: [WHAT_IF_SIMULATOR.md](WHAT_IF_SIMULATOR.md).

### `docs/`, `tests/`

- Architecture and design docs.
- Cross-cutting smoke/integration tests; backend unit tests live in `backend/tests/`.

---

## Implemented API surface (Phase 6)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness (does not require PostgreSQL) |
| `GET` | `/readiness` | Process + database connectivity |
| `GET` | `/api/customers` | Paginated customer list + latest **stored** prediction |
| `GET` | `/api/customers/{customer_id}` | Customer detail |
| `POST` | `/api/predict` | Score a stored customer; append to prediction history |
| `GET` | `/api/customers/{customer_id}/explanation` | Real SHAP explanation (`explained_output`: `log_odds`) |
| `POST` | `/api/recommendation` | Retention recommendation (`requires_human_approval`: true) |
| `POST` | `/api/what-if` | What-if simulation (model-based estimate, not causal) |
| `POST` | `/api/actions` | Create a **PENDING** review action |
| `GET` | `/api/actions` | List / filter actions |
| `GET` | `/api/actions/{action_id}` | Action detail |
| `PATCH` | `/api/actions/{action_id}` | Human review: APPROVED / MODIFIED / REJECTED |
| `GET` | `/api/overview` | Stored population and review counts |
| `GET` | `/api/model` | Trained model metadata (authenticated) |
| `GET` | `/api/me` | Backend-verified Auth0 identity and role |

`GET /health` is public. All `/api/*` routes require a valid Auth0 access
token. `POST /api/upload` remains deferred. Contracts and errors: [API.md](API.md).

---

## Shared data contracts

### Prediction

```json
{
  "customer_id": "C10293",
  "churn_probability": 0.87,
  "risk_level": "HIGH",
  "model_version": "v1.0",
  "top_drivers": [
    {
      "feature": "Contract",
      "impact": 0.42,
      "direction": "increases_risk"
    }
  ]
}
```

### Recommendation

```json
{
  "customer_id": "C10293",
  "recommendation": "Offer eligible annual-plan incentive and priority support",
  "reason": "The customer has high predicted churn risk associated with contract type, monthly charges and short tenure.",
  "priority": "HIGH",
  "confidence": "MEDIUM",
  "requires_human_approval": true
}
```

---

## Security & configuration

- All secrets via environment variables (`.env` locally; never committed).
- LLM keys exist only on the backend.
- Auth0 access tokens are validated on the API (signature, issuer, audience, expiry).
- CORS origins configured via `CORS_ORIGINS`. Production must use an explicit allowlist.
- Docker Compose provides local PostgreSQL 16, the API, and the frontend.
  Schema changes use Alembic. See [DATABASE.md](DATABASE.md).

---

## Reviewer dashboard (Phase 7)

The React application is a decision-support interface around the existing APIs.
It does not call an LLM, does not invent metrics, and does not execute retention
actions. The product story on every customer page is:

**Risk prediction → SHAP explanation → retention recommendation → what-if
estimate → human decision → action tracking.**

| Route | Page | Data source |
|-------|------|-------------|
| `/` | Overview | `GET /api/overview` (stored counts only) |
| `/customers` | Customer list | `GET /api/customers` (`q`, `risk_level`, pagination) |
| `/customers/:id` | Customer intelligence | profile, predict, explanation, recommendation, what-if, actions |
| `/actions` | Retention actions | `GET /api/actions` |
| `/model` | Model information | `GET /api/model` (public metadata subset) |

HTTP is isolated in `frontend/src/services/api.js`. The customer page sequences
calls in `useCustomerIntelligence` so the reviewer can see which stage is
running. What-if requests set `use_llm: false` so the comparison numbers stay
deterministic and the frontend never depends on a provider.

Human approval always starts from a `PENDING` action. Approve / modify / reject
are explicit `PATCH`es. The UI still labels **Reviewer mode**; the signed-in
Auth0 user and role appear next to it.

Local UI development: `cd frontend && npm install && npm run dev`. Leave
`VITE_API_BASE_URL` empty so Vite proxies `/api` and `/health` to
`http://127.0.0.1:8000`. Configure Auth0 as in [AUTHENTICATION.md](AUTHENTICATION.md).

## Current status (Phase 10)

PostgreSQL is the production database, with Alembic migrations, pooled
connections, and a public `/readiness` probe. Authentication remains Auth0
Universal Login. Still out of scope: upload pipeline, CRM integrations,
autonomous real-world actions, deployment.
