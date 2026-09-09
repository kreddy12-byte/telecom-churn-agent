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
# GitHub never contains *.joblib. Train the locked pipeline during build so
# prediction and SHAP work without a host volume. Keep the Telco CSV in the
# image so production startup can seed `customers` when the table is empty.
RUN python -m ml.src.training.train \
    && python -m ml.src.explainability.global_importance --no-plots

WORKDIR /workspace/backend

RUN chmod +x scripts/start.sh

EXPOSE 8000

# Migrations, then seed only if customers is empty, then serve.
# DATABASE_URL must be provided at runtime. Render injects PORT (default 10000).
CMD ["sh", "scripts/start.sh"]
