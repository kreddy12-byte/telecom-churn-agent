"""Provider-agnostic LLM interface.

Nothing above this layer knows which vendor is in use. Swapping OpenAI for a
local model, or for a future in-house service, means adding one class here and
changing an environment variable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMError(Exception):
    """Base class for provider failures. Always triggers deterministic fallback."""


class LLMUnavailableError(LLMError):
    """No usable provider: missing key, missing endpoint, or a network failure."""


class LLMTimeoutError(LLMError):
    """The provider did not answer within the configured timeout."""


class LLMResponseError(LLMError):
    """The provider answered, but the response was unusable."""


@dataclass(frozen=True)
class LLMCompletion:
    """A raw text completion plus the provenance needed for auditing."""

    text: str
    model: str
    provider: str

    @property
    def label(self) -> str:
        """Value recorded in ``RetentionRecommendation.provider``."""
        return f"{self.provider}:{self.model}"


class LLMProvider(ABC):
    """Minimal contract every LLM backend must satisfy."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """True when the provider is configured well enough to attempt a call.

        Checked before every call so a missing API key degrades to the
        deterministic engine instead of raising at import time.
        """

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> LLMCompletion:
        """Return the model's reply.

        Implementations must raise :class:`LLMTimeoutError`,
        :class:`LLMUnavailableError`, or :class:`LLMResponseError` — never a
        provider-specific exception — so callers can handle failures uniformly.
        """
