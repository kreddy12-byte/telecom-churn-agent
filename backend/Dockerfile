FROM python:3.12-slim

# libgomp is required by XGBoost / SHAP at import time even though this image
# never retrains the model.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace

COPY backend/requirements.txt backend/requirements.txt
COPY ml/requirements.txt ml/requirements.txt
COPY agent/requirements.txt agent/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt \
    && pip install --no-cache-dir -r ml/requirements.txt \
    && pip install --no-cache-dir -r agent/requirements.txt

COPY backend backend
COPY ml ml
COPY agent agent

WORKDIR /workspace/backend

EXPOSE 8000

# Production images apply migrations before serving. Local compose may wrap
# this with --reload; it still starts with `alembic upgrade head`.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
