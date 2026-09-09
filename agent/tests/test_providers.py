"""LLM provider abstraction tests.

Every test here uses an in-process mock transport. No test makes a real API call.
"""

from __future__ import annotations

import httpx
import pytest

from agent.config import AgentSettings
from agent.providers.base import LLMResponseError, LLMTimeoutError, LLMUnavailableError
from agent.providers.llm_provider import OpenAICompatibleProvider, build_provider


def make_provider(handler, **kwargs) -> OpenAICompatibleProvider:
    """Provider wired to a mock transport instead of the network."""
    client = httpx.Client(transport=httpx.MockTransport(handler))
    defaults = {"api_key": "test-key", "base_url": "https://llm.example/v1", "model": "test-model"}
    defaults.update(kwargs)
    return OpenAICompatibleProvider(client=client, **defaults)


def success_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"content": '{"strategy_id": "X"}'}}]}
    )


# =========================================================
# 1. AVAILABILITY
# =========================================================


def test_provider_without_api_key_is_unavailable() -> None:
    provider = OpenAICompatibleProvider(api_key="", base_url="https://x/v1", model="m")
    assert provider.is_available() is False


def test_unavailable_provider_raises_rather_than_calling_out() -> None:
    provider = OpenAICompatibleProvider(api_key="", base_url="", model="")
    with pytest.raises(LLMUnavailableError):
        provider.complete("system", "user")


# =========================================================
# 2. SUCCESSFUL CALL
# =========================================================


def test_successful_completion_returns_text_and_provenance() -> None:
    completion = make_provider(success_handler).complete("system", "user")

    assert completion.text == '{"strategy_id": "X"}'
    assert completion.model == "test-model"
    assert completion.label == "openai_compatible:test-model"


def test_request_carries_both_prompts_and_the_api_key() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        captured["body"] = request.read().decode()
        captured["url"] = str(request.url)
        return success_handler(request)

    make_provider(handler).complete("SYSTEM-RULES", "USER-EVIDENCE")

    assert captured["url"] == "https://llm.example/v1/chat/completions"
    assert captured["headers"]["authorization"] == "Bearer test-key"
    assert "SYSTEM-RULES" in captured["body"]
    assert "USER-EVIDENCE" in captured["body"]


# =========================================================
# 3. FAILURE MODES MAP ONTO THE SHARED EXCEPTION TYPES
# =========================================================


def test_timeout_is_translated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("too slow", request=request)

    with pytest.raises(LLMTimeoutError):
        make_provider(handler).complete("system", "user")


def test_transport_error_is_translated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(LLMUnavailableError):
        make_provider(handler).complete("system", "user")


def test_http_error_status_is_translated() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "overloaded"})

    with pytest.raises(LLMUnavailableError, match="503"):
        make_provider(handler).complete("system", "user")


def test_error_message_never_leaks_the_api_key() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    with pytest.raises(LLMUnavailableError) as error:
        make_provider(handler, api_key="super-secret-key").complete("system", "user")

    assert "super-secret-key" not in str(error.value)


@pytest.mark.parametrize(
    "body",
    [
        {"unexpected": "shape"},
        {"choices": []},
        {"choices": [{"message": {"content": ""}}]},
    ],
)
def test_malformed_response_is_translated(body: dict) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with pytest.raises(LLMResponseError):
        make_provider(handler).complete("system", "user")


# =========================================================
# 4. FACTORY / CONFIGURATION
# =========================================================


def test_factory_returns_none_when_the_llm_is_disabled() -> None:
    settings = AgentSettings(llm_provider="none", _env_file=None)
    assert build_provider(settings) is None


def test_factory_returns_none_when_the_api_key_is_missing() -> None:
    settings = AgentSettings(
        llm_provider="openai_compatible",
        llm_api_key="",
        llm_api_base_url="https://llm.example/v1",
        llm_model="test-model",
        _env_file=None,
    )
    assert settings.llm_configured is False
    assert build_provider(settings) is None


def test_factory_builds_a_configured_provider() -> None:
    settings = AgentSettings(
        llm_provider="openai_compatible",
        llm_api_key="test-key",
        llm_api_base_url="https://llm.example/v1",
        llm_model="test-model",
        _env_file=None,
    )
    provider = build_provider(settings)

    assert isinstance(provider, OpenAICompatibleProvider)
    assert provider.is_available() is True


def test_factory_rejects_an_unknown_provider_name() -> None:
    settings = AgentSettings(
        llm_provider="mystery_ai",
        llm_api_key="k",
        llm_api_base_url="https://llm.example/v1",
        llm_model="m",
        _env_file=None,
    )
    with pytest.raises(ValueError, match="Unknown LLM_PROVIDER"):
        build_provider(settings)
