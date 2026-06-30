"""Tests for the LLM provider abstraction (mock + factory + claude guard)."""

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
