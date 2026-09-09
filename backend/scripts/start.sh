#!/bin/sh
# Production container entrypoint (Render). WORKDIR is /workspace/backend
# and PYTHONPATH is /workspace, matching the image ENV.
set -eu

alembic upgrade head
python -m app.db.seed --if-empty
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
