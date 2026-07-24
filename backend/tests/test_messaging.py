"""Tests for the outbound WhatsApp messaging service (mocked HTTP)."""

import httpx
import pytest

from app.services.messaging import WhatsAppSendError, send_text


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_send_text_returns_message_id():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["auth"] = request.headers.get("Authorization")
        return httpx.Response(200, json={"messages": [{"id": "wamid.out1"}]})

    msg_id = send_text(
        "PN1", "+15551230000", "Hello!", access_token="test-token", client=_client(handler)
    )

    assert msg_id == "wamid.out1"
    assert captured["url"].endswith("/PN1/messages")
    assert captured["auth"] == "Bearer test-token"


def test_send_text_raises_on_4xx_without_retry():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"error": "bad number"})

    with pytest.raises(WhatsAppSendError):
        send_text("PN1", "bad", "Hi", access_token="test-token", client=_client(handler))
    assert calls["n"] == 1  # 4xx is not retried


def test_send_text_retries_on_5xx_then_fails():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(500)

    with pytest.raises(WhatsAppSendError):
        send_text(
            "PN1",
            "+15551230000",
            "Hi",
            access_token="test-token",
            client=_client(handler),
            max_attempts=3,
        )
    assert calls["n"] == 3  # retried up to max_attempts
