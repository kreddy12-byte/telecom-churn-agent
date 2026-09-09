"""Configuration for the retention agent.

Every value comes from environment variables. No API key, endpoint, or model
name is ever hardcoded, and none of these values are exposed to the frontend —
the agent runs strictly inside the backend process.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class AgentSettings(BaseSettings):
    """LLM and reasoning settings, loaded from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----------------------------------------------------------------- #
    # LLM provider
    # ----------------------------------------------------------------- #
    # "openai_compatible" covers OpenAI, Azure-compatible gateways, OpenRouter,
    # Groq, and local servers such as Ollama or vLLM that expose /chat/completions.
    # "none" disables the LLM entirely and forces the deterministic engine.
    llm_provider: str = "none"
    llm_api_key: str = ""
    llm_api_base_url: str = ""
    llm_model: str = ""

    # Low temperature: this is decision support, not creative writing.
    llm_temperature: float = 0.2
    llm_max_output_tokens: int = 700
    llm_timeout_seconds: float = 20.0

    # ----------------------------------------------------------------- #
    # Reasoning behaviour
    # ----------------------------------------------------------------- #
    # How many SHAP drivers the strategy engine evaluates. The report shows the
    # top few, but evaluation benefits from seeing more of the evidence.
    agent_evidence_driver_count: int = 10

    @property
    def llm_configured(self) -> bool:
        """True when enough settings are present to attempt an LLM call."""
        if self.llm_provider.strip().lower() in {"", "none", "disabled"}:
            return False
        return bool(self.llm_api_key and self.llm_api_base_url and self.llm_model)


@lru_cache
def get_agent_settings() -> AgentSettings:
    """Return cached agent settings."""
    return AgentSettings()
