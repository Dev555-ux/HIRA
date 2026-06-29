"""Deterministic mock LLM provider for development and tests.

Lets the entire orchestration loop run with no API key. By default it echoes a
grounded-looking reply derived from the latest user message; a fixed reply can
be injected for assertions.
"""

from __future__ import annotations

from app.ai.llm.base import ChatMessage, LLMProvider, LLMResponse


class MockProvider(LLMProvider):
    def __init__(self, fixed_reply: str | None = None, model: str = "mock-1"):
        self._fixed_reply = fixed_reply
        self._model = model

    def generate(
        self, *, system: str, messages: list[ChatMessage], max_tokens: int | None = None
    ) -> LLMResponse:
        if self._fixed_reply is not None:
            return LLMResponse(text=self._fixed_reply, model=self._model)
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        return LLMResponse(text=f"[mock reply] You asked: {last_user}", model=self._model)
