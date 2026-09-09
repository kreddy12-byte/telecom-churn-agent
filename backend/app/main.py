"""FastAPI application entrypoint.

# ============================================================
# 1. APPLICATION SETUP
# ============================================================

The backend is the sole integration layer: HTTP in, PostgreSQL and the locked
ML / agent / what-if packages out. Route modules stay thin; services own the
orchestration; repositories own SQL.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.exception_handlers import register_exception_handlers
from app.api.routes import (
    actions,
    customers,
    explanations,
    health,
    me,
    model_info,
    overview,
    predictions,
    recommendations,
    whatif,
)
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.session import reset_engine

configure_logging()
logger = get_logger(__name__)
settings = get_settings()

if not settings.cors_is_safe_for_environment():
    raise RuntimeError(
        "CORS_ORIGINS must be an explicit allowlist. Wildcard origins are not "
        "permitted when APP_ENV=production."
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Production DATABASE_URL is validated here so a bad deploy fails immediately
    # instead of serving traffic against SQLite. The engine itself is still
    # created lazily so /health does not require PostgreSQL to be up.
    get_settings().validate_database_url()
    logger.info("Starting %s (env=%s)", settings.app_name, settings.app_env)
    yield
    reset_engine()


# ============================================================
# 2. APP AND MIDDLEWARE
# ============================================================

app = FastAPI(
    title=settings.app_name,
    debug=settings.app_debug,
    version="0.6.0",
    description=(
        "Telecom churn intelligence API. The backend orchestrates the trained "
        "churn model, SHAP explanations, the retention agent, and the what-if "
        "simulator. It does not retrain the model, does not compute SHAP itself, "
        "        and never executes a real-world customer action. Every recommendation "
        "and simulation requires human approval (`requires_human_approval: true`)."
    ),
    lifespan=lifespan,
    openapi_tags=[
        {"name": "health", "description": "Liveness (/health) and readiness (/readiness)."},
        {"name": "customers", "description": "Stored Telco customer profiles."},
        {"name": "predictions", "description": "Churn scoring with history persistence."},
        {"name": "explanations", "description": "SHAP risk-driver explanations."},
        {
            "name": "recommendations",
            "description": "Evidence-grounded retention recommendations. Human approval required.",
        },
        {
            "name": "what-if",
            "description": (
                "Model-based what-if estimates — not causal predictions. "
                "Human approval required."
            ),
        },
        {
            "name": "actions",
            "description": "Human-review action tracking. No emails, plan changes, or CRM calls.",
        },
        {"name": "overview", "description": "Stored population and review counts."},
        {"name": "model", "description": "Facts about the locked trained model."},
        {"name": "auth", "description": "Authenticated identity from a verified Auth0 access token."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

# ============================================================
# 3. ROUTES
# ============================================================

# Health and readiness stay at the root so load balancers can probe them
# without the `/api` prefix. Everything else lives under the configured API prefix.
app.include_router(health.router)
app.include_router(me.router, prefix=settings.api_prefix)
app.include_router(customers.router, prefix=settings.api_prefix)
app.include_router(explanations.router, prefix=settings.api_prefix)
app.include_router(explanations.importance_router, prefix=settings.api_prefix)
app.include_router(predictions.router, prefix=settings.api_prefix)
app.include_router(recommendations.router, prefix=settings.api_prefix)
app.include_router(whatif.router, prefix=settings.api_prefix)
app.include_router(actions.router, prefix=settings.api_prefix)
app.include_router(overview.router, prefix=settings.api_prefix)
app.include_router(model_info.router, prefix=settings.api_prefix)