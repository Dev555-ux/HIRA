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
class ToolSchema:
    """A tool the model may call — name/description/JSON-schema parameters,
    the common shape both OpenAI-compatible (Groq) and Anthropic (Claude)
    tool-calling APIs accept with minimal reshaping. See app/ai/tools.py.

    `interaction_type` (DEC-050): "read" for a tool that only looks something
    up (e.g. check_availability) vs. "write" (the default) for anything that
    changes real state. app/ai/orchestrator.py's bounded round-trip uses this
    to resolve a proposed read tool inline and withhold it on the one
    follow-up call, generically across every domain — it never needs to know
    a specific tool's name, only this field."""

    name: str
    description: str
    parameters: dict
    interaction_type: Literal["read", "write"] = "write"


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class LLMResponse:
    text: str
    model: str
    raw: Any | None = field(default=None, repr=False)
    tool_calls: list[ToolCall] | None = None


class LLMError(RuntimeError):
    """Raised when generation fails after retries, or on misconfiguration."""


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        max_tokens: int | None = None,
        tools: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        """Generate a reply given a system prompt and conversation messages.

        If `tools` is given and the model chooses to call one, the returned
        LLMResponse.tool_calls is non-empty (LLMResponse.text may be empty).
        """
