"""Claude (Anthropic) LLM provider.

Wraps the Anthropic Messages API behind the LLMProvider interface, with bounded
retries on transient errors and logging. The Anthropic SDK is imported lazily so
the rest of the app never hard-depends on it. Requires ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import logging
import time

from app.ai.llm.base import ChatMessage, LLMError, LLMProvider, LLMResponse, ToolCall, ToolSchema

logger = logging.getLogger(__name__)


def _to_anthropic_tools(tools: list[ToolSchema]) -> list[dict]:
    """Anthropic's Messages API tool shape: {"name", "description", "input_schema"}
    — "input_schema" instead of OpenAI-compatible "parameters"."""
    return [
        {"name": tool.name, "description": tool.description, "input_schema": tool.parameters}
        for tool in tools
    ]


class ClaudeProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        default_max_tokens: int = 1024,
        max_attempts: int = 3,
    ):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set; cannot use the Claude provider")
        from anthropic import Anthropic  # lazy import — no hard dependency app-wide

        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._default_max_tokens = default_max_tokens
        self._max_attempts = max_attempts

    def generate(
        self,
        *,
        system: str,
        messages: list[ChatMessage],
        max_tokens: int | None = None,
        tools: list[ToolSchema] | None = None,
    ) -> LLMResponse:
        from anthropic import APIConnectionError, APIStatusError, RateLimitError

        payload_messages = [{"role": m.role, "content": m.content} for m in messages]
        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                resp = self._client.messages.create(
                    model=self._model,
                    max_tokens=max_tokens or self._default_max_tokens,
                    system=system,
                    messages=payload_messages,
                    **({"tools": _to_anthropic_tools(tools)} if tools else {}),
                )
                text = "".join(block.text for block in resp.content if block.type == "text")
                tool_calls = [
                    ToolCall(id=block.id, name=block.name, arguments=block.input)
                    for block in resp.content
                    if block.type == "tool_use"
                ] or None
                return LLMResponse(text=text, model=self._model, raw=resp, tool_calls=tool_calls)
            except (APIConnectionError, RateLimitError) as exc:
                last_error = exc
                logger.warning("Claude transient error (attempt %d): %s", attempt, exc)
                if attempt < self._max_attempts:
                    time.sleep(0.5 * attempt)
            except APIStatusError as exc:
                if exc.status_code >= 500:
                    last_error = exc
                    logger.warning("Claude 5xx (attempt %d): %s", attempt, exc)
                    if attempt < self._max_attempts:
                        time.sleep(0.5 * attempt)
                        continue
                raise LLMError(f"Claude rejected the request: {exc}") from exc

        raise LLMError(f"Claude failed after {self._max_attempts} attempts: {last_error}")
