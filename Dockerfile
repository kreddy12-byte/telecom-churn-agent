# Production FastAPI image for platforms that look for ./Dockerfile (Render).
#
# Build context MUST be the repository root. This file is intentionally at the
# root because Render's default Dockerfile Path is ./Dockerfile; the existing
# backend/Dockerfile is the same layout used by local docker compose.
#
# Git does not store *.joblib. This image trains the locked pipeline during
# build so prediction and SHAP work without a host volume.

FROM python:3.12-slim

# libgomp is required by XGBoost / SHAP at import time even though this image
# never retrains the model at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace

# --- Dependencies (layer-cached unless requirement files change) ---
COPY backend/requirements.txt backend/requirements.txt
COPY ml/requirements.txt ml/requirements.txt
COPY agent/requirements.txt agent/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && pip install --no-cache-dir -r ml/requirements.txt \
    && pip install --no-cache-dir -r agent/requirements.txt

# --- Application packages (imports stay as ml.*, agent.*, app.*) ---
COPY backend backend
COPY ml ml
COPY agent agent

# --- Model artifacts ---
# GitHub never contains *.joblib. Train the existing locked pipeline, cache
# shap_background.joblib so explanations do not need the raw CSV, then drop
# the downloaded dataset from the image.
RUN python -m ml.src.training.train \
    && python -m ml.src.explainability.global_importance --no-plots \
    && rm -f ml/data/raw/telco_customer_churn.csv

WORKDIR /workspace/backend

EXPOSE 8000

# Render injects PORT (default 10000). Local docker run without PORT stays on 8000.
# Migrations run before serve; DATABASE_URL must be provided at runtime.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
