"""Concrete LLM provider plus the factory that selects one from configuration.

``OpenAICompatibleProvider`` speaks the ``/chat/completions`` API used by OpenAI
and by most gateways and local servers (OpenRouter, Groq, Ollama, vLLM, LM
Studio). Pointing the agent at a different backend is a change to
``LLM_API_BASE_URL`` and ``LLM_MODEL``, not a code change.

Credentials come from environment variables only, are read inside the backend
process, and are never logged or returned to a caller.
"""

from __future__ import annotations

from typing import Any

import httpx

from agent.config import AgentSettings, get_agent_settings
from agent.providers.base import (
    LLMCompletion,
    LLMProvider,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
)

CHAT_COMPLETIONS_PATH = "/chat/completions"


class OpenAICompatibleProvider(LLMProvider):
    """Chat-completions client for any OpenAI-compatible endpoint."""

    name = "openai_compatible"

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float = 0.2,
        max_output_tokens: int = 700,
        timeout_seconds: float = 20.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._temperature = temperature
        self._max_output_tokens = max_output_tokens
        self._timeout_seconds = timeout_seconds
        # Injectable so tests can exercise transport behaviour without network.
        self._client = client

    # =========================================================
    # 1. AVAILABILITY
    # =========================================================

    def is_available(self) -> bool:
        return bool(self._api_key and self._base_url and self._model)

    # =========================================================
    # 2. REQUEST
    # =========================================================

    def _build_payload(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self._temperature,
            "max_tokens": self._max_output_tokens,
            # Ask for JSON where the backend supports it; the reasoning service
            # still parses defensively because not every gateway honours this.
            "response_format": {"type": "json_object"},
        }

    def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        if not self.is_available():
            raise LLMUnavailableError(
                "LLM provider is not configured (missing API key, base URL, or model)."
            )

        url = f"{self._base_url}{CHAT_COMPLETIONS_PATH}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        client = self._client or httpx.Client(timeout=self._timeout_seconds)
        should_close = self._client is None
        try:
            response = client.post(
                url, json=self._build_payload(system_prompt, user_prompt), headers=headers
            )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(
                f"LLM request timed out after {self._timeout_seconds}s."
            ) from exc
        except httpx.HTTPError as exc:
            # Deliberately does not include the URL or headers, to keep any
            # credential material out of logs and error payloads.
            raise LLMUnavailableError(f"LLM request failed: {type(exc).__name__}") from exc
        finally:
            if should_close:
                client.close()

        return self._parse_response(response)

    # =========================================================
    # 3. RESPONSE HANDLING
    # =========================================================

    def _parse_response(self, response: httpx.Response) -> LLMCompletion:
        if response.status_code >= 400:
            raise LLMUnavailableError(
                f"LLM provider returned HTTP {response.status_code}."
            )

        try:
            body = response.json()
            text = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMResponseError(f"Unexpected LLM response shape: {exc}") from exc

        if not isinstance(text, str) or not text.strip():
            raise LLMResponseError("LLM returned an empty message.")

        return LLMCompletion(text=text, model=self._model, provider=self.name)


# =========================================================
# 4. FACTORY
# =========================================================


def build_provider(settings: AgentSettings | None = None) -> LLMProvider | None:
    """Return a configured provider, or None when the LLM is disabled.

    Returning None rather than raising is deliberate: an unconfigured
    environment must still produce recommendations through the deterministic
    engine, which is the documented default for local development.
    """
    resolved = settings or get_agent_settings()

    if not resolved.llm_configured:
        return None

    provider_name = resolved.llm_provider.strip().lower()
    if provider_name != OpenAICompatibleProvider.name:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{resolved.llm_provider}'. "
            f"Supported providers: '{OpenAICompatibleProvider.name}', 'none'."
        )

    return OpenAICompatibleProvider(
        api_key=resolved.llm_api_key,
        base_url=resolved.llm_api_base_url,
        model=resolved.llm_model,
        temperature=resolved.llm_temperature,
        max_output_tokens=resolved.llm_max_output_tokens,
        timeout_seconds=resolved.llm_timeout_seconds,
    )
