# Telecom Customer Churn Intelligence & Retention Agent

Decision-support application for telecom reviewers. It scores churn risk, explains the prediction, recommends a retention action, simulates interventions, and records a human decision.

**Predict → Explain → Recommend → Simulate → Decide**

The FastAPI backend is the only integration layer. The React frontend never talks to the database, ML artifacts, or an LLM provider.

> Local Auth0 login needs both `127.0.0.1` and `localhost` callback URLs in the Auth0 SPA settings. See [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md).

---

## Key capabilities

- Churn probability and HIGH / MEDIUM / LOW risk from a trained sklearn model
- Per-customer SHAP drivers (influence on this prediction, not proof of cause)
- Retention recommendation from a controlled strategy engine, with optional LLM wording
- Model-based what-if estimates for eligible interventions
- Human approve / modify / reject, persisted as retention actions
- Auth0 Universal Login; FastAPI validates access tokens (RS256, issuer, audience, expiry)

If no LLM is configured, recommendations still work using the deterministic fallback engine.

---

## Architecture

```
React (Vite)  →  FastAPI  →  ML (predict / SHAP)
                          →  Agent (recommend / what-if)
                          →  PostgreSQL
```

| Area | Role |
|------|------|
| `frontend/` | Reviewer UI |
| `backend/` | HTTP API, auth, persistence |
| `ml/` | Training, prediction, SHAP |
| `agent/` | Strategy catalogue, recommendation, what-if |
| `docs/` | Design notes |

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

---

## Tech stack

| Layer | Stack |
|-------|--------|
| Frontend | React, Vite, JavaScript, Tailwind CSS, Recharts, Axios, Auth0 SPA SDK |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL |
| ML | Pandas, NumPy, Scikit-learn, XGBoost, SHAP, Joblib |
| Agent | Deterministic strategy engine; optional OpenAI-compatible LLM |
| Local ops | Docker Compose |

---

## Local setup

Prerequisites: Python 3.11+ (3.12 recommended), Node.js 18+, Docker Desktop (PostgreSQL).

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Fill Auth0 domain, SPA client ID, and audience in both files. Never put an Auth0 client secret or LLM key in the frontend file.

### Database

```bash
docker compose up -d db
```

Local defaults (development only): user `churn_user`, database `telecom_churn`, host `127.0.0.1:5432`. Production must use its own credentials. Schema notes: [docs/DATABASE.md](docs/DATABASE.md).

From a virtualenv at the repo root:

```bash
pip install -r backend/requirements.txt
pip install -r ml/requirements.txt
pip install -r agent/requirements.txt
```

### ML artifacts

Trained binaries (`*.joblib`) and the Telco CSV are git-ignored. Recreate them locally:

```bash
python -m ml.src.data.download_dataset
python -m ml.src.training.train
python -m ml.src.explainability.global_importance
```

Pipeline notes: [docs/ML_PIPELINE.md](docs/ML_PIPELINE.md).

### Backend

```bash
cd backend
alembic upgrade head
python -m app.db.seed
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- Health: http://127.0.0.1:8000/health
- Readiness: http://127.0.0.1:8000/readiness
- OpenAPI: http://127.0.0.1:8000/docs

API reference: [docs/API.md](docs/API.md).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI: http://127.0.0.1:5173 (Vite proxies `/api` and `/health` to port 8000 when `VITE_API_BASE_URL` is empty).

### Full stack (Docker)

```bash
docker compose up --build
```

API http://127.0.0.1:8000, UI http://127.0.0.1:8080. For a production-shaped overlay that does not publish Postgres on the host: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build`.

---

## Environment variables

Templates: `.env.example`, `backend/.env.example`, `frontend/.env.example`.

| Variable | Where | Purpose |
|----------|--------|---------|
| `DATABASE_URL` | backend | PostgreSQL SQLAlchemy URL |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | compose | Local Docker Postgres |
| `CORS_ORIGINS` | backend | Allowed browser origins |
| `AUTH0_DOMAIN` / `AUTH0_AUDIENCE` / `AUTH0_ISSUER` | backend | JWT validation |
| `LLM_PROVIDER` / `LLM_API_KEY` | backend only | `none` or `openai_compatible` |
| `VITE_API_BASE_URL` | frontend | Leave blank for the Vite proxy |
| `VITE_AUTH0_DOMAIN` / `VITE_AUTH0_CLIENT_ID` / `VITE_AUTH0_AUDIENCE` | frontend | Public SPA settings only |

Auth0 client secrets, database passwords, and LLM keys must never appear in frontend env files.

---

## Authentication

Auth0 Universal Login issues an access token. FastAPI validates RS256, issuer, audience, and expiry. A valid token opens the application. REVIEWER / ADMIN on the namespaced roles claim is a badge only; a missing role does not block access.

Configure **both** origins in the Auth0 Dashboard:

- Callback: `http://127.0.0.1:5173/callback`, `http://localhost:5173/callback`
- Logout / Web Origins: `http://127.0.0.1:5173`, `http://localhost:5173`

Full setup: [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md).

---

## Tests

```bash
cd frontend && npm test
cd backend && pytest -q
python -m pytest ml/tests -q
python -m pytest agent/tests -q
```

ML tests that need the trained model skip automatically if artifacts are missing.

---

## Deployment overview

Not deployed from this audit.

1. Train or supply `ml/models/*.joblib` (not stored in git).
2. Run PostgreSQL; set `DATABASE_URL`; `alembic upgrade head`; seed if needed.
3. Set backend Auth0 domain/audience and CORS origins. `APP_ENV=production` refuses SQLite.
4. Build the frontend with public `VITE_AUTH0_*` values. Do not bake a client secret.
5. Optional LLM: set `LLM_PROVIDER` and `LLM_API_KEY` on the backend only.

The agent never contacts a customer. Approval records a human decision only.
