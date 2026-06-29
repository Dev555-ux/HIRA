"""LLM provider interface and response abstraction.

The application depends only on `LLMProvider` and `LLMResponse` — never on the
Anthropic SDK (or any vendor) directly. New providers (OpenAI, Gemini,
OpenRouter, local) are added by implementing this interface; no business logic
changes. See app/ai/llm/__init__.py for the factory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

Role = Literal["user", "assistant"]


@dataclass
class ChatMessage:
    role: Role
    content: str


@dataclass
class LLMResponse:
    text: str
    model: str
    raw: Any | None = field(default=None, repr=False)


class LLMError(RuntimeError):
    """Raised when generation fails after retries, or on misconfiguration."""


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self, *, system: str, messages: list[ChatMessage], max_tokens: int | None = None
    ) -> LLMResponse:
        """Generate a reply given a system prompt and conversation messages."""
