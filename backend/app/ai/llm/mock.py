"""Deterministic mock LLM provider for development and tests.

Lets the entire orchestration loop run with no API key. By default it echoes a
grounded-looking reply derived from the latest user message; a fixed reply (or
fixed tool calls, for tool-calling tests — DEC-032) can be injected for
assertions.
"""

from __future__ import annotations

from app.ai.llm.base import ChatMessage, LLMProvider, LLMResponse, ToolCall, ToolSchema


class MockProvider(LLMProvider):
    def __init__(
        self,
        fixed_reply: str | None = None,
        model: str = "mock-1",
        fixed_tool_calls: list[ToolCall] | None = None,
    ):
        self._fixed_reply = fixed_reply
        self._model = model
        self._fixed_tool_calls = fixed_tool_calls

    def generate(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        max_tokens: int | None = None,
        tools: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        if self._fixed_reply is not None:
            return LLMResponse(
                text=self._fixed_reply, model=self._model, tool_calls=self._fixed_tool_calls
            )
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        return LLMResponse(
            text=f"[mock reply] You asked: {last_user}",
            model=self._model,
            tool_calls=self._fixed_tool_calls,
        )
