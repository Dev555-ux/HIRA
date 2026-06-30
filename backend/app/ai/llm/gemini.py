"""Gemini (Google) LLM provider.

Wraps the official google-genai SDK behind the LLMProvider interface, with
bounded retries on transient (5xx/server) errors and logging. The SDK is
imported lazily so the rest of the app never hard-depends on it. Requires
GEMINI_API_KEY.

Role mapping: our ChatMessage uses "user"/"assistant"; Gemini uses "user"/"model".
The system prompt is passed via system_instruction (not as a message).
"""

from __future__ import annotations

import logging
import time

from app.ai.llm.base import ChatMessage, LLMError, LLMProvider, LLMResponse

logger = logging.getLogger(__name__)

_ROLE_MAP = {"user": "user", "assistant": "model"}


class GeminiProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        *,
        default_max_tokens: int = 1024,
        max_attempts: int = 3,
    ):
        if not api_key:
            raise LLMError("GEMINI_API_KEY is not set; cannot use the Gemini provider")
        from google import genai  # lazy import — no hard dependency app-wide

        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._default_max_tokens = default_max_tokens
        self._max_attempts = max_attempts

    def generate(
        self, *, system: str, messages: list[ChatMessage], max_tokens: int | None = None
    ) -> LLMResponse:
        from google.genai import errors, types

        contents = [{"role": _ROLE_MAP[m.role], "parts": [{"text": m.content}]} for m in messages]
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens or self._default_max_tokens,
        )

        last_error: Exception | None = None
        for attempt in range(1, self._max_attempts + 1):
            try:
                resp = self._client.models.generate_content(
                    model=self._model, contents=contents, config=config
                )
                return LLMResponse(text=resp.text or "", model=self._model, raw=resp)
            except errors.ServerError as exc:
                last_error = exc
                logger.warning("Gemini transient error (attempt %d): %s", attempt, exc)
                if attempt < self._max_attempts:
                    time.sleep(0.5 * attempt)
            except errors.ClientError as exc:
                # 429 (rate limit / quota) is transient; other 4xx are not.
                if getattr(exc, "code", None) == 429:
                    last_error = exc
                    logger.warning("Gemini rate-limited (attempt %d): %s", attempt, exc)
                    if attempt < self._max_attempts:
                        time.sleep(0.5 * attempt)
                        continue
                    raise LLMError(f"Gemini rate limit/quota exceeded: {exc}") from exc
                raise LLMError(f"Gemini rejected the request: {exc}") from exc

        raise LLMError(f"Gemini failed after {self._max_attempts} attempts: {last_error}")
