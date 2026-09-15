"""Groq LLM provider.

Uses the official `groq` SDK (OpenAI-compatible chat completions) behind the
LLMProvider interface. Bounded retries on transient errors (connection,
timeout, 429, 5xx); other 4xx are not retried. SDK imported lazily so the rest
of the app never hard-depends on it. Requires GROQ_API_KEY.

Sprint 80 follow-up (production smoke test, DEC-049): also bounded-retries
Groq's `tool_use_failed` 400 — this is Groq's own tool-call parser rejecting
a completion where the model emitted a function call as literal text (e.g.
`<function=check_availability(...)>`) instead of the structured tool-calling
channel, for llama-3.3-70b-versatile in particular. It's a stochastic
decoding hiccup, not a malformed request on our side (the same tool schemas
succeed on a retry), so it gets the same bounded-retry treatment as a 5xx
rather than failing the turn outright. Any other 4xx is still not retried.

Chat format maps directly: our ChatMessage roles ("user"/"assistant") are used
as-is, with the system prompt prepended as a "system" message.
"""

from __future__ import annotations

import json
import logging
import time

from app.ai.llm.base import ChatMessage, LLMError, LLMProvider, LLMResponse, ToolCall, ToolSchema

logger = logging.getLogger(__name__)


def _to_chat_messages(system: str, messages: list[ChatMessage]) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}]
    out.extend({"role": m.role, "content": m.content} for m in messages)
    return out


def _to_openai_tools(tools: list[ToolSchema]) -> list[dict]:
    """Groq's chat completions API is OpenAI-compatible — tools use the
    {"type": "function", "function": {...}} wrapper shape."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            },
        }
        for tool in tools
    ]


def _parse_tool_calls(message) -> list[ToolCall] | None:
    if not getattr(message, "tool_calls", None):
        return None
    return [
        ToolCall(
            id=tc.id,
            name=tc.function.name,
            arguments=json.loads(tc.function.arguments) if tc.function.arguments else {},
        )
        for tc in message.tool_calls
    ]


class GroqProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        default_max_tokens: int = 1024,
        max_attempts: int = 3,
    ):
        if not api_key:
            raise LLMError("GROQ_API_KEY is not set; cannot use the Groq provider")
        from groq import Groq  # lazy import — no hard dependency app-wide

        self._client = Groq(api_key=api_key)
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
        from groq import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

        payload = _to_chat_messages(system, messages)
        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=payload,
                    max_tokens=max_tokens or self._default_max_tokens,
                    **({"tools": _to_openai_tools(tools)} if tools else {}),
                )
                message = resp.choices[0].message
                return LLMResponse(
                    text=message.content or "",
                    model=self._model,
                    raw=resp,
                    tool_calls=_parse_tool_calls(message),
                )
            except (APIConnectionError, APITimeoutError, RateLimitError) as exc:
                last_error = exc
                logger.warning("Groq transient error (attempt %d): %s", attempt, exc)
                if attempt < self._max_attempts:
                    time.sleep(0.5 * attempt)
            except APIStatusError as exc:
                if exc.status_code >= 500:
                    last_error = exc
                    logger.warning("Groq 5xx (attempt %d): %s", attempt, exc)
                    if attempt < self._max_attempts:
                        time.sleep(0.5 * attempt)
                        continue
                    raise LLMError(f"Groq rejected the request: {exc}") from exc
                error_code = (
                    exc.body.get("error", {}).get("code") if isinstance(exc.body, dict) else None
                )
                if error_code == "tool_use_failed":
                    last_error = exc
                    logger.warning("Groq tool_use_failed (attempt %d): %s", attempt, exc)
                    if attempt < self._max_attempts:
                        time.sleep(0.5 * attempt)
                        continue
                raise LLMError(f"Groq rejected the request: {exc}") from exc

        raise LLMError(f"Groq failed after {self._max_attempts} attempts: {last_error}")
