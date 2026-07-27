"""Tests for the LLM provider abstraction (mock + factory + claude guard)."""

import httpx
import pytest

from app.ai.llm import ChatMessage, LLMError, _PROVIDERS, get_llm_provider
from app.ai.llm.base import LLMProvider
from app.ai.llm.claude import ClaudeProvider
from app.ai.llm.groq import GroqProvider, _to_chat_messages
from app.ai.llm.mock import MockProvider


def test_factory_returns_mock_by_default():
    provider = get_llm_provider("mock")
    assert isinstance(provider, MockProvider)
    assert isinstance(provider, LLMProvider)


def test_factory_unknown_provider_raises():
    with pytest.raises(LLMError):
        get_llm_provider("does-not-exist")


def test_mock_returns_fixed_reply():
    provider = MockProvider(fixed_reply="We're open 9-5.")
    resp = provider.generate(system="s", messages=[ChatMessage(role="user", content="hi")])
    assert resp.text == "We're open 9-5."


def test_mock_echoes_last_user_message_by_default():
    provider = MockProvider()
    resp = provider.generate(
        system="s",
        messages=[
            ChatMessage(role="user", content="first"),
            ChatMessage(role="assistant", content="ok"),
            ChatMessage(role="user", content="are you open?"),
        ],
    )
    assert "are you open?" in resp.text


def test_claude_provider_requires_api_key():
    with pytest.raises(LLMError):
        ClaudeProvider(api_key="", model="claude-sonnet-4-6")


def test_groq_is_registered_in_factory():
    assert "groq" in _PROVIDERS


def test_groq_provider_requires_api_key():
    with pytest.raises(LLMError):
        GroqProvider(api_key="", model="llama-3.3-70b-versatile")


def test_groq_prepends_system_message():
    msgs = _to_chat_messages(
        "system rules",
        [ChatMessage(role="user", content="hi"), ChatMessage(role="assistant", content="hello")],
    )
    assert msgs[0] == {"role": "system", "content": "system rules"}
    assert msgs[1] == {"role": "user", "content": "hi"}
    assert msgs[2] == {"role": "assistant", "content": "hello"}


# --- Sprint 80 follow-up: bounded retry on Groq's tool_use_failed 400 ------
#
# Live production smoke test hit Groq rejecting llama-3.3-70b-versatile's
# completion with a 400 `tool_use_failed` — the model emitted the function
# call as literal text (`<function=check_availability(...)>`) instead of
# using the structured tool-calling channel. A retry with the identical
# request reliably recovers (it's a stochastic decoding hiccup, not a
# malformed request on our side), so this gets the same bounded-retry
# treatment as a 5xx rather than failing the whole turn.


class _FakeMessage:
    def __init__(self, content="", tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _FakeCompletionResponse:
    def __init__(self, content):
        self.choices = [type("_Choice", (), {"message": _FakeMessage(content=content)})()]


class _FakeCompletions:
    def __init__(self, side_effects):
        self._side_effects = list(side_effects)
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        effect = self._side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeGroqClient:
    def __init__(self, side_effects):
        self.chat = _FakeChat(_FakeCompletions(side_effects))


def _tool_use_failed_error():
    from groq import BadRequestError

    response = httpx.Response(400, request=httpx.Request("POST", "https://api.groq.com/x"))
    return BadRequestError(
        "Failed to call a function.",
        response=response,
        body={"error": {"message": "Failed to call a function.", "code": "tool_use_failed"}},
    )


def _unrelated_400_error():
    from groq import BadRequestError

    response = httpx.Response(400, request=httpx.Request("POST", "https://api.groq.com/x"))
    return BadRequestError(
        "bad request",
        response=response,
        body={"error": {"message": "bad request", "code": "invalid_request_error"}},
    )


def test_groq_retries_and_recovers_from_a_tool_use_failed_400():
    provider = GroqProvider(api_key="test-key", model="llama-3.3-70b-versatile", max_attempts=3)
    client = _FakeGroqClient([_tool_use_failed_error(), _FakeCompletionResponse("We have a slot at 3pm.")])
    provider._client = client

    resp = provider.generate(system="s", messages=[ChatMessage(role="user", content="book it")])

    assert resp.text == "We have a slot at 3pm."
    assert client.chat.completions.calls == 2


def test_groq_gives_up_after_max_attempts_of_tool_use_failed():
    provider = GroqProvider(api_key="test-key", model="llama-3.3-70b-versatile", max_attempts=2)
    client = _FakeGroqClient([_tool_use_failed_error(), _tool_use_failed_error()])
    provider._client = client

    with pytest.raises(LLMError):
        provider.generate(system="s", messages=[ChatMessage(role="user", content="book it")])

    assert client.chat.completions.calls == 2


def test_groq_does_not_retry_an_unrelated_400():
    provider = GroqProvider(api_key="test-key", model="llama-3.3-70b-versatile", max_attempts=3)
    client = _FakeGroqClient([_unrelated_400_error()])
    provider._client = client

    with pytest.raises(LLMError):
        provider.generate(system="s", messages=[ChatMessage(role="user", content="hi")])

    assert client.chat.completions.calls == 1
