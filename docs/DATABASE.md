# Database

Retention Intelligence persists application data in **PostgreSQL 16** in any
production-like environment. SQLAlchemy 2 repositories stay the only SQL
boundary. The CSV is never stored; only typed customer rows, append-only
predictions, human-review actions, and Auth0 profile cache rows are kept.

```
FastAPI  →  repositories  →  SQLAlchemy engine (pool)  →  PostgreSQL
```

Development and pytest may use **explicit** SQLite (`DATABASE_URL=sqlite://...`).
`APP_ENV=production` **refuses** SQLite. There is no silent fallback.

---

## Architecture

| Table | Role |
|---|---|
| `customers` | Telco dataset features. PK = `customer_id` (dataset `customerID`) |
| `predictions` | Append-only scores (`customer_id`, probability, risk, model version, time) |
| `actions` | PENDING → APPROVED / MODIFIED / REJECTED. Auth0 `sub` is the reviewer key |
| `app_users` | Local profile cache keyed by `auth0_sub`. Not an identity provider |

Timestamps are timezone-aware UTC. Check constraints enforce action statuses
and prediction risk bands. Foreign keys cascade from `customers`.

---

## Environment

All of these come from the environment. Nothing is hardcoded in application code.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy URL. Production: `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE` |
| `APP_ENV` | `development` / `testing` / `production` |
| `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` / `DB_POOL_TIMEOUT` / `DB_POOL_RECYCLE` | Connection pool |
| `DB_CONNECT_TIMEOUT` | Seconds to wait for a TCP connect |
| `DB_SSLMODE` | Empty locally. Use `require` or `verify-full` on managed PostgreSQL |
| `DB_ECHO` | SQL echo. Ignored in production |

`postgresql+psycopg2://` remains accepted. Never put `DATABASE_URL` in API
responses or logs.

---

## Local setup

```bash
docker compose up -d db
cp backend/.env.example backend/.env
# DATABASE_URL already points at 127.0.0.1:5432 for the compose database

cd backend
alembic upgrade head
python -m app.db.seed                 # idempotent; safe to rerun
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

SQLite demo (not production):

```bash
cd backend
set DATABASE_URL=sqlite:///./local_demo.db
set APP_ENV=development
python -m app.db.init_db
python -m app.db.seed
```

---

## Migrations

Production schema changes are Alembic revisions. `create_all` is development
and test convenience only.

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

The live URL is read from `DATABASE_URL` in `alembic/env.py`. Do not put a
password in `alembic.ini`.

---

## Seed

```bash
cd backend
python -m app.db.seed
python -m app.db.seed --limit 100
python -m app.db.seed --if-empty   # skip when customers already exist
```

- Reads the Telco CSV from disk; does **not** store the file in PostgreSQL
- Upserts on `customer_id` — a second run updates, it does not duplicate
- `--if-empty` inserts only when the table has zero rows (Render startup)
- Does not load the churn label (training ground truth, not a customer attribute)
- Does not write or delete `predictions` or `actions`

---

## Health vs readiness

| Path | Meaning |
|---|---|
| `GET /health` | Process is up. **Does not** query the database. Public. Contract unchanged: `{"status":"healthy"}` |
| `GET /readiness` | Process **and** database. `200 {"status":"ready"}` or `503 database_unavailable` |

Neither response includes the DSN, password, or driver traceback.

---

## Docker

```bash
docker compose up --build
```

Services: `db` (Postgres 16), `backend` (Alembic then uvicorn), `frontend`
(nginx on port 8080, proxies `/api` and `/health`). PostgreSQL is bound to
`127.0.0.1:5432` only. Seed locally with `docker compose exec backend python -m app.db.seed`.

The Render production image (`Dockerfile` at the repo root) starts with
`scripts/start.sh`: `alembic upgrade head`, then `python -m app.db.seed --if-empty`,
then Uvicorn. The Telco CSV is left in the image so that first boot can fill
an empty `customers` table. Later deploys skip seed when rows already exist.

Production-shaped overlay (no host port for Postgres):

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up --build
```

---

## Troubleshooting

| Symptom | What to check |
|---|---|
| Startup error mentioning SQLite in production | `APP_ENV=production` with a sqlite `DATABASE_URL`. Point it at PostgreSQL |
| `DATABASE_URL is not set` | Copy `backend/.env.example` to `backend/.env` |
| `503 database_unavailable` | Postgres down, wrong host, or SSL required (`DB_SSLMODE=require`) |
| Seed inserts 0, updates 7043 | Already seeded; this is the idempotent path |
| Render batch `processed: 0` | `customers` empty — first-boot seed failed or CSV missing from the image |
| Alembic `Can't locate revision` | Run commands from `backend/` |

---

## Production requirements

1. PostgreSQL (16+ recommended), not SQLite
2. `alembic upgrade head` before traffic (the Render start script does this)
3. `DB_SSLMODE=require` (or `verify-full`) on managed providers
4. Do not publish `5432` on a public interface
5. Credentials only in the environment — no secret manager in this phase
