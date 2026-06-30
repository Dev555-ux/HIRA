"""Tests for the LLM provider abstraction (mock + factory + claude guard)."""

import pytest

from app.ai.llm import ChatMessage, LLMError, get_llm_provider
from app.ai.llm import _PROVIDERS
from app.ai.llm.base import LLMProvider
from app.ai.llm.claude import ClaudeProvider
from app.ai.llm.gemini import GeminiProvider
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


def test_gemini_is_registered_in_factory():
    assert "gemini" in _PROVIDERS


def test_gemini_provider_requires_api_key():
    with pytest.raises(LLMError):
        GeminiProvider(api_key="", model="gemini-2.0-flash")


def test_gemini_maps_assistant_role_to_model():
    # Role mapping is part of the contract; verify without any network call.
    from app.ai.llm.gemini import _ROLE_MAP

    assert _ROLE_MAP == {"user": "user", "assistant": "model"}
