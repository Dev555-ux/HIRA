"""Sprint 65 PR 1 — InstagramProvider foundation checks; Sprint 65 PR 5
adds outbound send() checks against a mocked Graph API.

No database anywhere in this file — matching
`tests/test_whatsapp_provider.py`'s DB-free contract (send() tests use a
mocked `httpx` transport, same convention as that file's own outbound
section). Covers what's genuinely implemented (capabilities, routing key,
signature verification, subscription handshake, best-effort payload
parsing, outbound send) and asserts `validate_credentials()` — still a
documented placeholder, see `provider.py`'s module docstring for why —
raises `NotImplementedError` rather than silently returning a fabricated
result.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import httpx
import pytest

from app.channels.base.capabilities import Capability
from app.channels.base.credentials import ChannelCredentials
from app.channels.base.errors import WebhookVerificationFailedError
from app.channels.base.message import OutboundMessage
from app.channels.instagram import InstagramProvider
from app.channels.instagram.parsing import parse_inbound_payload, signature_valid
from app.channels.registry import ChannelRegistry
from app.core.config import settings

APP_SECRET = "test-instagram-app-secret"


def _sign(body: bytes, secret: str = APP_SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _webhook_payload(
    business_account_id="IG_ACCT_1",
    sender_id="IGSID_123",
    message_id="mid.1",
    text="Hi there",
):
    return {
        "object": "instagram",
        "entry": [
            {
                "id": business_account_id,
                "time": 1700000000,
                "messaging": [
                    {
                        "sender": {"id": sender_id},
                        "recipient": {"id": business_account_id},
                        "timestamp": 1700000000,
                        "message": {"mid": message_id, "text": text},
                    }
                ],
            }
        ],
    }


@pytest.fixture
def provider() -> InstagramProvider:
    return InstagramProvider()


# --- construction & registration -------------------------------------------


def test_provider_channel_id():
    assert InstagramProvider().channel_id == "instagram"


def test_registry_registration():
    registry = ChannelRegistry()
    provider = InstagramProvider()
    registry.register(provider)
    assert registry.get("instagram") is provider
    assert registry.available() == ("instagram",)


def test_default_registry_exposes_both_channels_once_both_are_imported():
    import app.channels.instagram  # noqa: F401
    import app.channels.whatsapp  # noqa: F401
    from app.channels.registry import get_default_registry

    assert set(get_default_registry().available()) >= {"whatsapp", "instagram"}


# --- capability reporting ---------------------------------------------------


def test_capabilities_are_text_only(provider):
    """TEXT only, as of Sprint 65 PR 5 — a direct read of what send()/
    parsing.py actually implement end to end, same reasoning as
    WhatsAppProvider's own capability set (see capabilities()'s docstring).
    Every other capability stays False — not a platform limitation, a
    statement that nothing else is built and tested yet."""
    caps = provider.capabilities()
    assert caps.channel == "instagram"
    assert caps.supports(Capability.TEXT) is True
    for capability in Capability:
        if capability is Capability.TEXT:
            continue
        assert caps.supports(capability) is False, f"{capability} should not be advertised yet"


# --- routing key ---------------------------------------------------------


def test_extract_routing_key_returns_the_business_account_id(provider):
    payload = _webhook_payload(business_account_id="IG_ACCT_42")
    raw_body = json.dumps(payload).encode()

    assert provider.extract_routing_key(raw_body) == "IG_ACCT_42"


def test_extract_routing_key_malformed_json_raises(provider):
    with pytest.raises(WebhookVerificationFailedError):
        provider.extract_routing_key(b"not json")


def test_extract_routing_key_missing_account_id_raises(provider):
    with pytest.raises(WebhookVerificationFailedError):
        provider.extract_routing_key(b"{}")


# --- webhook signature -------------------------------------------------


def test_verify_webhook_signature_valid(provider):
    raw_body = json.dumps(_webhook_payload()).encode()
    header = _sign(raw_body)
    creds = ChannelCredentials(channel="instagram", access_token="tok", secret=APP_SECRET)

    assert (
        provider.verify_webhook_signature({"X-Hub-Signature-256": header}, raw_body, creds) is True
    )


def test_verify_webhook_signature_wrong_secret_rejected(provider):
    raw_body = json.dumps(_webhook_payload()).encode()
    header = _sign(raw_body, secret="wrong-secret")
    creds = ChannelCredentials(channel="instagram", access_token="tok", secret=APP_SECRET)

    assert (
        provider.verify_webhook_signature({"X-Hub-Signature-256": header}, raw_body, creds) is False
    )


def test_verify_webhook_signature_no_secret_on_credentials_rejected(provider):
    raw_body = json.dumps(_webhook_payload()).encode()
    header = _sign(raw_body)
    creds = ChannelCredentials(channel="instagram", access_token="tok", secret=None)

    assert (
        provider.verify_webhook_signature({"X-Hub-Signature-256": header}, raw_body, creds) is False
    )


def test_signature_valid_matches_whatsapps_algorithm_by_construction():
    """Not a shared implementation (see parsing.py's module docstring —
    providers are self-contained on purpose) but the same HMAC-SHA256
    scheme, so the two must agree on any given input."""
    from app.channels.whatsapp.parsing import signature_valid as whatsapp_signature_valid

    raw_body = b'{"object":"instagram"}'
    header = _sign(raw_body)
    assert signature_valid(raw_body, header, APP_SECRET) == whatsapp_signature_valid(
        raw_body, header, APP_SECRET
    )


# --- subscription handshake -------------------------------------------------


def test_verify_subscription_echoes_challenge_on_match(provider, monkeypatch):
    monkeypatch.setattr(settings, "instagram_verify_token", "shared-ig-verify-token")
    creds = ChannelCredentials(channel="instagram", access_token="unused")

    result = provider.verify_subscription(
        {
            "hub.mode": "subscribe",
            "hub.verify_token": "shared-ig-verify-token",
            "hub.challenge": "123",
        },
        creds,
    )

    assert result == "123"


def test_verify_subscription_wrong_token_returns_none(provider, monkeypatch):
    monkeypatch.setattr(settings, "instagram_verify_token", "shared-ig-verify-token")
    creds = ChannelCredentials(channel="instagram", access_token="unused")

    result = provider.verify_subscription(
        {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "123"}, creds
    )

    assert result is None


def test_verify_subscription_does_not_reuse_whatsapps_verify_token(provider, monkeypatch):
    """Regression guard: verify_subscription() must check
    settings.instagram_verify_token, not settings.whatsapp_verify_token —
    the two are deliberately separate settings (see config.py's comment)."""
    monkeypatch.setattr(settings, "whatsapp_verify_token", "whatsapp-token")
    monkeypatch.setattr(settings, "instagram_verify_token", "instagram-token")
    creds = ChannelCredentials(channel="instagram", access_token="unused")

    result = provider.verify_subscription(
        {"hub.mode": "subscribe", "hub.verify_token": "whatsapp-token", "hub.challenge": "123"},
        creds,
    )

    assert result is None  # WhatsApp's token must not satisfy Instagram's handshake


# --- payload parsing ---------------------------------------------------


def test_parse_webhook_normalizes_a_text_message(provider):
    payload = _webhook_payload(sender_id="IGSID_7", message_id="mid.7", text="Are you open?")
    messages = provider.parse_webhook(json.dumps(payload).encode())

    assert len(messages) == 1
    message = messages[0]
    assert message.channel == "instagram"
    assert message.external_conversation_id == "IGSID_7"
    assert message.external_sender_id == "IGSID_7"
    assert message.external_message_id == "mid.7"
    assert message.text == "Are you open?"
    assert message.sender_display_name is None  # never available from the webhook alone
    assert message.media == ()


def test_parse_webhook_normalizes_multiple_messages_in_one_delivery(provider):
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IG_ACCT_1",
                "messaging": [
                    {"sender": {"id": "IGSID_1"}, "message": {"mid": "mid.1", "text": "First"}},
                    {"sender": {"id": "IGSID_2"}, "message": {"mid": "mid.2", "text": "Second"}},
                ],
            }
        ],
    }
    messages = provider.parse_webhook(json.dumps(payload).encode())

    assert [m.external_message_id for m in messages] == ["mid.1", "mid.2"]
    assert [m.text for m in messages] == ["First", "Second"]


def test_parse_webhook_ignores_an_unknown_event_type_without_crashing(provider, caplog):
    """Meta adding a new event shape (e.g. a reaction, no `message` key)
    must never crash the parser — recognized as "not a message" and
    debug-logged, same as a read receipt (Sprint 65 PR 3)."""
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IG_ACCT_1",
                "messaging": [
                    {
                        "sender": {"id": "IGSID_1"},
                        "reaction": {"mid": "mid.1", "action": "react", "emoji": "❤"},
                    }
                ],
            }
        ],
    }
    with caplog.at_level("DEBUG", logger="app.channels.instagram.parsing"):
        messages = provider.parse_webhook(json.dumps(payload).encode())

    assert messages == []
    assert any("Skipping non-message" in record.message for record in caplog.records)


def test_parse_webhook_malformed_json_raises(provider):
    with pytest.raises(WebhookVerificationFailedError):
        provider.parse_webhook(b"not json")


def test_parse_inbound_payload_skips_non_message_events():
    """A read receipt (no `message` key) is recognized and skipped, not
    turned into an empty NormalizedMessage — mirrors WhatsApp's
    status-callback skip."""
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IG_ACCT_1",
                "messaging": [
                    {
                        "sender": {"id": "IGSID_1"},
                        "recipient": {"id": "IG_ACCT_1"},
                        "read": {"mid": "mid.1"},
                    }
                ],
            }
        ],
    }
    assert parse_inbound_payload(payload) == []


@pytest.mark.parametrize(
    "message",
    [
        {"mid": "mid.1", "attachments": [{"type": "image", "payload": {"url": "https://x"}}]},
        {"mid": "mid.2", "is_deleted": True},
        {"mid": "mid.3"},  # no text, no attachments — genuinely empty message
    ],
)
def test_unsupported_message_shapes_normalize_to_empty_text(message):
    """Documented as unsupported in parsing.py's module docstring — these
    still produce a NormalizedMessage (something was received), just with
    an empty body, the same "unsupported -> empty, not fatal" convention
    WhatsApp's parser established."""
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IG_ACCT_1",
                "messaging": [{"sender": {"id": "IGSID_1"}, "message": message}],
            }
        ],
    }
    messages = parse_inbound_payload(payload)
    assert len(messages) == 1
    assert messages[0].text == ""


# --- documented placeholders -------------------------------------------


def test_validate_credentials_raises_not_implemented(provider):
    creds = ChannelCredentials(
        channel="instagram", access_token="tok", external_account_id="IG_ACCT_1"
    )
    with pytest.raises(NotImplementedError):
        provider.validate_credentials(creds)


# --- outbound send, against a mocked Graph API (Sprint 65 PR 5) -------------


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _outbound(text="hi") -> OutboundMessage:
    return OutboundMessage(channel="instagram", external_conversation_id="IGSID_1", text=text)


def _creds(external_account_id="PAGE_1") -> ChannelCredentials:
    return ChannelCredentials(
        channel="instagram", access_token="page-token", external_account_id=external_account_id
    )


def test_send_success_returns_delivery_receipt(provider):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v21.0/PAGE_1/messages"
        assert request.headers["Authorization"] == "Bearer page-token"
        import json as _json

        body = _json.loads(request.content)
        assert body == {
            "recipient": {"id": "IGSID_1"},
            "message": {"text": "hi"},
            "messaging_type": "RESPONSE",
        }
        return httpx.Response(200, json={"recipient_id": "IGSID_1", "message_id": "mid.sent-1"})

    from app.channels.instagram.send import send_instagram_message

    receipt = send_instagram_message(_outbound(), _creds(), client=_client(handler))

    assert receipt.status == "sent"
    assert receipt.external_message_id == "mid.sent-1"


@pytest.mark.parametrize("code", [190, 10, 100])
def test_send_non_retryable_meta_error_codes(provider, code):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": {"message": "some raw graph detail xyz123", "code": code}}
        )

    from app.channels.instagram.send import send_instagram_message

    receipt = send_instagram_message(_outbound(), _creds(), client=_client(handler))

    assert receipt.status == "failed"
    assert receipt.retryable is False
    # Never leaks Meta's raw error message/body — only the status + code.
    assert "xyz123" not in (receipt.error or "")


@pytest.mark.parametrize("code", [4, 32])
def test_send_retryable_meta_error_codes(provider, code):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": {"message": "rate limited", "code": code}})

    from app.channels.instagram.send import send_instagram_message

    receipt = send_instagram_message(_outbound(), _creds(), client=_client(handler))

    assert receipt.status == "failed"
    assert receipt.retryable is True


def test_send_unmapped_error_code_defaults_to_non_retryable(provider):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, json={"error": {"message": "??", "code": 999999}})

    from app.channels.instagram.send import send_instagram_message

    receipt = send_instagram_message(_outbound(), _creds(), client=_client(handler))

    assert receipt.status == "failed"
    assert receipt.retryable is False


def test_send_5xx_is_retryable(provider):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    from app.channels.instagram.send import send_instagram_message

    receipt = send_instagram_message(_outbound(), _creds(), client=_client(handler))

    assert receipt.status == "failed"
    assert receipt.retryable is True


def test_send_network_failure_is_retryable(provider):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    from app.channels.instagram.send import send_instagram_message

    receipt = send_instagram_message(_outbound(), _creds(), client=_client(handler))

    assert receipt.status == "failed"
    assert receipt.retryable is True


def test_send_malformed_success_response_is_non_retryable(provider):
    """A 2xx status but a body that doesn't match Meta's documented shape
    — Meta most likely already accepted the message, so retrying risks a
    duplicate send to a real customer."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    from app.channels.instagram.send import send_instagram_message

    receipt = send_instagram_message(_outbound(), _creds(), client=_client(handler))

    assert receipt.status == "failed"
    assert receipt.retryable is False


def test_send_missing_external_account_id_fails_without_calling_out(provider):
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("should not make an HTTP call without a Page id")

    from app.channels.instagram.send import send_instagram_message

    receipt = send_instagram_message(
        _outbound(), _creds(external_account_id=None), client=_client(handler)
    )

    assert receipt.status == "failed"
    assert receipt.retryable is False


def test_provider_send_delegates_to_send_instagram_message(provider, monkeypatch):
    """InstagramProvider.send() is a thin delegation — one transport
    attempt, no retry loop, no persistence (verified by construction: this
    module never imports a database session). Patches `httpx.Client.post`
    at the transport level, same convention as
    tests/test_ai_reply_worker_idempotency.py::_stub_whatsapp_transport,
    since `provider.send()` takes no client-injection seam of its own."""

    def fake_post(self, url, *, headers=None, json=None, **kwargs):
        return httpx.Response(200, json={"recipient_id": "IGSID_1", "message_id": "mid.1"})

    monkeypatch.setattr(httpx.Client, "post", fake_post)

    receipt = provider.send(_outbound(), _creds())

    assert receipt.status == "sent"
    assert receipt.external_message_id == "mid.1"
