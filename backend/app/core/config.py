"""Application configuration loaded from environment variables.

Nothing here has a secret as its default. Credentials arrive from the
environment or not at all, and the LLM settings are read by the agent layer's
own settings object — they are listed here only so a single ``.env`` file can
drive the whole backend process.
"""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the FastAPI backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        populate_by_name=True,
        protected_namespaces=("settings_",),
    )

    app_name: str = "Telecom Churn Agent API"
    app_env: str = "development"
    app_debug: bool = False
    api_prefix: str = "/api"

    # --- Database (credentials only from the environment; never hardcoded) ---
    database_url: str = ""
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800
    db_connect_timeout: int = 5
    # Empty keeps the driver default. Managed PostgreSQL typically needs
    # ``require`` or ``verify-full``. Never log this with the DSN.
    db_sslmode: str = ""

    # --- Pagination ---
    # Capped so a single request cannot ask the database for the whole table.
    default_page_size: int = 20
    max_page_size: int = 100

    # --- CORS — comma-separated origins in env. Never use * in production. ---
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- LLM (backend-only; never exposed to the frontend) ---
    # The agent layer owns these; duplicated here so one .env configures both.
    llm_provider: str = "none"
    llm_api_key: str = ""
    llm_api_base_url: str = ""
    llm_model: str = ""

    # --- ML artifacts ---
    # Empty means "use the ML package's own default location", which is the
    # normal case; set it only when artifacts live outside the repository.
    # MODEL_PATH is accepted as an alias so the existing .env.example still works.
    ml_models_dir: str = Field(
        default="",
        validation_alias=AliasChoices("ML_MODELS_DIR", "MODEL_PATH", "ml_models_dir"),
    )
    # Informational only. The trained artifact's own metadata is the source of
    # truth for the version string returned on predictions.
    model_version: str = "1.0.0"

    # --- Explanations ---
    # SHAP drivers returned by the explanation endpoint.
    explanation_top_k: int = 5

    # --- Auth0 (JWT validation). Domain/audience/issuer are not secrets. ---
    # Client secrets and Management API tokens must never be set here.
    auth0_domain: str = ""
    auth0_audience: str = ""
    auth0_issuer: str = ""
    # Namespaced claim copied onto the access token by an Auth0 Post-Login Action.
    auth0_roles_claim: str = "https://retention-intelligence.app/roles"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def auth0_issuer_url(self) -> str:
        """Issuer used for JWT validation, always with a trailing slash."""
        raw = (self.auth0_issuer or "").strip()
        if not raw and self.auth0_domain:
            raw = f"https://{self.auth0_domain.strip().rstrip('/')}/"
        if raw and not raw.endswith("/"):
            raw = f"{raw}/"
        return raw

    def cors_is_safe_for_environment(self) -> bool:
        """Production must not use a wildcard origin allowlist."""
        origins = self.cors_origin_list
        if self.app_env.lower() != "production":
            return bool(origins)
        return bool(origins) and "*" not in origins

    @property
    def models_dir_or_none(self) -> str | None:
        """Artifact directory override, or None to use the ML default."""
        return self.ml_models_dir.strip() or None

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    @property
    def allows_sqlite(self) -> bool:
        """SQLite is for development/testing only, and only when DATABASE_URL says so."""
        return not self.is_production

    def validate_database_url(self) -> str:
        """Return a usable DATABASE_URL or raise with a credential-free message.

        Production never falls back to SQLite. A missing or non-Postgres URL
        fails loudly so a deploy cannot silently run against a file database.
        """
        from app.db.url import database_url_backend

        url = (self.database_url or "").strip()
        backend = database_url_backend(url)
        if backend == "missing":
            raise RuntimeError(
                "DATABASE_URL is not set. Development may use an explicit "
                "sqlite:/// path; production must use "
                "postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE."
            )
        if self.is_production:
            if backend == "sqlite":
                raise RuntimeError(
                    "APP_ENV=production refuses SQLite. Set DATABASE_URL to a "
                    "PostgreSQL URL (postgresql+psycopg://...). There is no "
                    "silent SQLite fallback."
                )
            if backend != "postgresql":
                raise RuntimeError(
                    "APP_ENV=production requires a PostgreSQL DATABASE_URL "
                    "(postgresql+psycopg:// or postgresql+psycopg2://)."
                )
            return url
        if backend not in {"sqlite", "postgresql"}:
            raise RuntimeError(
                "DATABASE_URL must be a SQLite URL (development/testing) or a "
                "PostgreSQL URL (postgresql+psycopg://...)."
            )
        return url


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
