"""LLM provider factory.

`get_llm_provider()` returns the configured provider (default: mock). To go
live with Claude: set ANTHROPIC_API_KEY and LLM_PROVIDER=claude in the
environment — no code change.

To add a provider (OpenAI, Gemini, OpenRouter, local, etc.): implement LLMProvider in
this package and register it in `_PROVIDERS`. No business logic changes.
"""

from __future__ import annotations

from functools import lru_cache

from app.ai.llm.base import ChatMessage, LLMError, LLMProvider, LLMResponse
from app.ai.llm.claude import ClaudeProvider
from app.ai.llm.groq import GroqProvider
from app.ai.llm.mock import MockProvider
from app.core.config import settings


def _build_claude() -> LLMProvider:
    return ClaudeProvider(
        api_key=settings.anthropic_api_key,
        model=settings.llm_model,
        default_max_tokens=settings.llm_max_tokens,
    )


def _build_groq() -> LLMProvider:
    return GroqProvider(
        api_key=settings.groq_api_key,
        model=settings.groq_model,
        default_max_tokens=settings.llm_max_tokens,
    )


_PROVIDERS = {
    "mock": lambda: MockProvider(),
    "claude": _build_claude,
    "groq": _build_groq,
}


@lru_cache(maxsize=None)
def get_llm_provider(name: str | None = None) -> LLMProvider:
    name = name or settings.llm_provider
    factory = _PROVIDERS.get(name)
    if factory is None:
        raise LLMError(f"Unknown LLM provider '{name}'. Known: {sorted(_PROVIDERS)}")
    return factory()


__all__ = [
    "ChatMessage",
    "LLMError",
    "LLMProvider",
    "LLMResponse",
    "get_llm_provider",
]
