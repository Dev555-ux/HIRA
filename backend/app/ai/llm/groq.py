"""Groq LLM provider.

Uses the official `groq` SDK (OpenAI-compatible chat completions) behind the
LLMProvider interface. Bounded retries on transient errors (connection,
timeout, 429, 5xx); other 4xx are not retried. SDK imported lazily so the rest
of the app never hard-depends on it. Requires GROQ_API_KEY.

Chat format maps directly: our ChatMessage roles ("user"/"assistant") are used
as-is, with the system prompt prepended as a "system" message.
"""

from __future__ import annotations

import logging
import time

from app.ai.llm.base import ChatMessage, LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


def _to_chat_messages(system: str, messages: list[ChatMessage]) -> list[dict]:
    out: list[dict] = [{"role": "system", "content": system}]
    out.extend({"role": m.role, "content": m.content} for m in messages)
    return out


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
        self, *, system: str, messages: list[ChatMessage], max_tokens: int | None = None
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
                )
                text = resp.choices[0].message.content or ""
                return LLMResponse(text=text, model=self._model, raw=resp)
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

        raise LLMError(f"Groq failed after {self._max_attempts} attempts: {last_error}")
