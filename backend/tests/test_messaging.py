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


# --- Critical audit fix #2, Part A: exception normalization -----------------


def test_send_text_raises_whatsapp_send_error_on_malformed_json_without_retry():
    """A 200 with a body that isn't valid JSON at all (json.JSONDecodeError,
    a ValueError subclass) must surface as WhatsAppSendError, not the raw
    parsing exception — and must not retry, since a 2xx means Meta most
    likely already sent the message; re-POSTing risks a duplicate send."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, content=b"not valid json{{{")

    with pytest.raises(WhatsAppSendError) as exc_info:
        send_text("PN1", "+15551230000", "Hi", access_token="test-token", client=_client(handler))

    assert calls["n"] == 1  # not retried
    assert "not a well-formed send confirmation" in str(exc_info.value)


@pytest.mark.parametrize(
    "body",
    [
        {},  # missing "messages" entirely -> KeyError
        {"messages": []},  # empty list -> IndexError
        {"messages": "oops"},  # not a list -> TypeError once ["id"] is applied
        {"messages": [{}]},  # missing "id" -> KeyError
        [],  # a JSON array instead of an object -> TypeError on ["messages"]
    ],
)
def test_send_text_raises_whatsapp_send_error_on_unexpected_payload_shape(body):
    """Every unexpected-but-valid-JSON shape Meta could plausibly return on
    a 200 must be normalized the same way as malformed JSON — not leak a
    raw KeyError/IndexError/TypeError to the caller."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=body)

    with pytest.raises(WhatsAppSendError):
        send_text("PN1", "+15551230000", "Hi", access_token="test-token", client=_client(handler))
    assert calls["n"] == 1  # not retried


def test_send_text_retries_then_raises_whatsapp_send_error_on_timeout():
    """A timeout (httpx.TimeoutException, a TransportError/RequestError
    subclass) is retried like a 5xx, and — once attempts are exhausted —
    surfaces as WhatsAppSendError, never the raw httpx exception."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(WhatsAppSendError):
        send_text(
            "PN1",
            "+15551230000",
            "Hi",
            access_token="test-token",
            client=_client(handler),
            max_attempts=3,
        )
    assert calls["n"] == 3  # retried up to max_attempts, like a 5xx


def test_send_text_retries_on_connection_error():
    """A dropped connection (httpx.ConnectError, also a TransportError
    subclass) is retried the same way — and a later attempt can still
    succeed within the same call."""
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 2:
            raise httpx.ConnectError("connection refused", request=request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.out1"}]})

    msg_id = send_text(
        "PN1",
        "+15551230000",
        "Hi",
        access_token="test-token",
        client=_client(handler),
        max_attempts=3,
    )

    assert msg_id == "wamid.out1"
    assert calls["n"] == 2


def test_send_text_wraps_a_completely_unexpected_exception():
    """Safety net: even an exception type this module never anticipated
    must still surface as WhatsAppSendError — the one contract callers can
    rely on (see this module's own docstring)."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise RuntimeError("something this module never anticipated")

    with pytest.raises(WhatsAppSendError) as exc_info:
        send_text("PN1", "+15551230000", "Hi", access_token="test-token", client=_client(handler))

    assert "Unexpected error" in str(exc_info.value)
