# Backend API

The FastAPI backend is the only integration layer in this project. It exposes
the locked ML, SHAP, retention-agent, and what-if engines over HTTP and persists
customers, prediction history, and human-review actions in PostgreSQL.

It does **not** retrain the model, recompute SHAP, invent retention strategies,
or execute any real-world customer action.

---

## Runtime

```
HTTP request
    → route (validation only)
        → service (orchestration)
            → repository (SQL) and/or ml/ / agent/ (intelligence)
                → PostgreSQL  |  trained artifacts
```

LLM API keys are loaded by the agent settings object from environment variables
and injected into services through a FastAPI dependency. Route handlers never
read, hold, or log a key.

Human approval is a schema invariant:

- every recommendation has `requires_human_approval: true`
- every what-if result has `requires_human_approval: true`
- every action is created in `PENDING` and becomes `APPROVED` only through an
  explicit `PATCH`

---

## Database schema

Four tables. Production applies them with Alembic (`alembic upgrade head`).
Development and tests may still call `python -m app.db.init_db` (`create_all`).
Production **refuses** `create_all` and **refuses** SQLite. Details:
[DATABASE.md](DATABASE.md).

### `customers`

Natural key: the Telco dataset's `customerID`. Columns are the features the
trained model actually consumes, stored in snake_case. Translation back to the
dataset names (`MonthlyCharges`, `Contract`, …) lives in one place:
`Customer.to_model_record()`.

| Column | Notes |
|---|---|
| `customer_id` | Primary key |
| `gender`, `senior_citizen`, `partner`, `dependents` | Demographics |
| `tenure`, `contract`, `paperless_billing`, `payment_method` | Account |
| `phone_service`, `multiple_lines`, `internet_service` | Services |
| `online_security`, `online_backup`, `device_protection` | |
| `tech_support`, `streaming_tv`, `streaming_movies` | |
| `monthly_charges`, `total_charges` | `total_charges` is nullable (blank for brand-new accounts) |
| `created_at`, `updated_at` | |

### `predictions`

Append-only history. A customer may have many rows; nothing is updated in place.

| Column | Notes |
|---|---|
| `id` | Surrogate key |
| `customer_id` | FK → `customers` |
| `churn_probability`, `risk_level`, `model_version` | Copied from the ML layer |
| `created_at` | |

### `actions`

Human decisions. Creating a row cannot set it to `APPROVED`.

| Column | Notes |
|---|---|
| `id` | Surrogate key |
| `customer_id` | FK → `customers` |
| `strategy_id`, `recommendation` | What was proposed |
| `status` | `PENDING` \| `APPROVED` \| `MODIFIED` \| `REJECTED` |
| `reviewer_note` | Required for `MODIFIED` and `REJECTED` |
| `reviewed_by_sub` | Auth0 `sub` of the reviewer (authoritative identity; nullable on PENDING) |
| `reviewed_by_email`, `reviewed_by_name` | Display/audit only; not the identity key |
| `created_at`, `updated_at` | |

Allowed transitions:

```
PENDING  →  APPROVED | MODIFIED | REJECTED
MODIFIED →  APPROVED | REJECTED
APPROVED →  (terminal)
REJECTED →  (terminal)
```

### `app_users`

Local profile cache for an Auth0 subject. Passwords are never stored.

| Column | Notes |
|---|---|
| `id` | Surrogate key |
| `auth0_sub` | Unique; authoritative identity |
| `email`, `name`, `picture_url` | Display |
| `role` | Last role seen on a verified token (authorization still uses the JWT) |
| `created_at`, `last_seen_at` | |

---

## Seed

```bash
cd backend
alembic upgrade head          # production and shared PostgreSQL
python -m app.db.init_db      # development/testing convenience only
python -m app.db.seed              # all ~7,043 Telco customers
python -m app.db.seed --limit 100  # smaller local set
python -m app.db.seed --if-empty   # no-op when customers already exist
```

The CSV is never stored in PostgreSQL. Seeding is idempotent: `customer_id` is the
primary key, so a second run updates existing rows instead of inserting
duplicates. `--if-empty` skips entirely when the table is not empty and does
not modify predictions or actions. The churn label is not loaded — it is
training ground truth, not a customer attribute.

---

## Endpoints

Error body (every failure):

```json
{
  "error": {
    "code": "customer_not_found",
    "message": "Customer '0000-XXXXX' was not found.",
    "details": { "customer_id": "0000-XXXXX" }
  }
}
```

Messages never contain stack traces, connection strings, API keys, or headers.

Interactive docs: `http://localhost:8000/docs`

### `GET /health`

Liveness. Does not touch the database, so a Postgres outage does not take the
process down. Contract: `{"status": "healthy"}`.

### `GET /readiness`

Deploy probe. Runs `SELECT 1` against the configured database.

```json
{ "status": "ready" }
```

`503 database_unavailable` when the database cannot be reached. The body never
includes the DSN or driver traceback.

### `GET /api/customers?limit=20&offset=0&q=&risk_level=`

Paginated list. Each item includes `latest_prediction` and `latest_action` when
those rows have been **stored**. Optional `q` is a case-insensitive substring
of `customer_id`. Optional `risk_level` keeps customers whose latest stored
prediction is in that band. This endpoint never runs the model.

### `GET /api/overview`

Stored counts only: customer population, evaluated customers, latest-prediction
risk bands, action statuses, and recent HIGH-risk customers. Never runs the
model.

### `GET /api/model`

Public subset of `model_metadata.json` (name, version, metrics, dataset size,
explainability). Filesystem paths and environment details are omitted.

### `GET /api/customers/{customer_id}`

Full profile — every feature the churn model consumes — plus the latest stored
prediction. `404 customer_not_found` when absent.

### `POST /api/predict`

```json
{ "customer_id": "7590-VHVEG" }
```

Loads the stored record, calls the existing explainer (which calls the existing
predictor), appends a `predictions` row, and returns the Step 1/2 contract plus
SHAP `top_drivers`:

```json
{
  "customer_id": "7590-VHVEG",
  "churn_probability": 0.8064,
  "risk_level": "HIGH",
  "prediction": 1,
  "model_version": "1.0.0",
  "top_drivers": [
    { "feature": "tenure", "value": 1, "impact": 0.xxxx, "direction": "increases_risk", "shap_value": 1.3752 }
  ],
  "predicted_at": "2026-09-08T..."
}
```

`404` unknown customer. `422` unscoreable record. `503` missing model artifacts.

### `GET /api/customers/{customer_id}/explanation?top_k=5`

Real SHAP explanation. `explained_output` is always `"log_odds"`. The numbers
are produced by `ml.src.explainability.explainer.explain_customer`; the API
does not recompute them.

### `POST /api/recommendation`

```json
{ "customer_id": "7590-VHVEG", "detailed": false }
```

Compact contract (default):

```json
{
  "customer_id": "7590-VHVEG",
  "recommendation": "...",
  "reason": "...",
  "priority": "HIGH",
  "confidence": "MEDIUM",
  "requires_human_approval": true
}
```

Set `detailed: true` for the full agent output (selected strategy, reasoning,
SHAP-backed evidence, confidence rationale, limitations, provider provenance).
With no LLM configured the deterministic engine writes the prose and labels
`provider = "deterministic_fallback"`.

### `POST /api/what-if`

```json
{
  "customer_id": "7590-VHVEG",
  "scenario_ids": ["annual_contract", "two_year_contract"],
  "use_llm": true
}
```

Omit `scenario_ids` to evaluate every applicable catalogue scenario. Optional
`custom_scenarios` pass through the same validator as catalogue entries.

The response is the simulator's `WhatIfResult`: baseline, scenarios, SHAP
comparisons, ranking, recommended scenario, AI interpretation, limitations.
Every payload includes:

> Model-based what-if estimate — not a causal prediction.

`requires_human_approval` is always `true`. Unknown scenario ids return
`400 invalid_scenario`. Inapplicable scenarios are listed in
`rejected_scenarios` rather than aborting the comparison.

### `GET /api/me`

Returns the verified Auth0 subject, email, name, picture, and effective role
(`ADMIN` or `REVIEWER`). Requires a valid access token.

### `POST /api/actions`

```json
{
  "customer_id": "7590-VHVEG",
  "strategy_id": "CONTRACT_CONVERSION",
  "recommendation": "...",
  "reviewer_note": null
}
```

Always created as `PENDING` (`201`). No email, SMS, CRM call, or plan change
occurs.

### `GET /api/actions?customer_id=&status=&limit=20&offset=0`

Newest first. Filter by customer and/or status.

### `GET /api/actions/{action_id}`

### `PATCH /api/actions/{action_id}`

```json
{ "status": "APPROVED" }
```

```json
{ "status": "REJECTED", "reviewer_note": "Customer already leaving." }
```

```json
{
  "status": "MODIFIED",
  "reviewer_note": "Offer support instead of a contract incentive.",
  "recommendation": "Revised wording."
}
```

`409 invalid_action_transition` for illegal moves (for example re-deciding an
already-approved action). `422 reviewer_note_required` for `MODIFIED` /
`REJECTED` without a note.

Approve / modify / reject persist the verified Auth0 identity on the action
(`reviewed_by_sub`, `reviewed_by_email`, `reviewed_by_name`). Those fields are
null on `PENDING` rows and on records created before authentication.

Protected `/api` routes return `401 unauthenticated` without a valid bearer
token. `GET /health` and `GET /readiness` do not require a token.

---

## Local run

```bash
# One virtualenv at the repo root, with all three requirement files:
pip install -r backend/requirements.txt
pip install -r ml/requirements.txt
pip install -r agent/requirements.txt

cp backend/.env.example backend/.env   # edit DATABASE_URL if needed

docker compose up -d db
cd backend
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or the full stack (Postgres + API + frontend):

```bash
docker compose up --build
```

The backend container runs `alembic upgrade head` before uvicorn. Seed
separately: `docker compose exec backend python -m app.db.seed`.

The Render production `Dockerfile` keeps the Telco CSV and starts via
`backend/scripts/start.sh` (`alembic upgrade head`, then
`python -m app.db.seed --if-empty`, then Uvicorn).

`GET /health` does not require Postgres. `GET /readiness` and endpoints that
read or write data return `503 database_unavailable` if the database is down,
without leaking the DSN.

---

## Configuration

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy URL. Production: `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE` |
| `DB_SSLMODE` / `DB_POOL_*` / `DB_CONNECT_TIMEOUT` | TLS and pooling. See [DATABASE.md](DATABASE.md). |
| `CORS_ORIGINS` | Comma-separated browser origins. Never `*` in production. |
| `AUTH0_DOMAIN` / `AUTH0_AUDIENCE` / `AUTH0_ISSUER` | Access-token validation. No client secret. |
| `AUTH0_ROLES_CLAIM` | Access-token role claim. Default `https://retention-intelligence.app/roles` |
| `LLM_PROVIDER` | `none` (deterministic engine) or `openai_compatible` |
| `LLM_API_KEY` / `LLM_API_BASE_URL` / `LLM_MODEL` | Backend only |
| `ML_MODELS_DIR` / `MODEL_PATH` | Optional artifact-directory override |

Never commit a real `.env`.
