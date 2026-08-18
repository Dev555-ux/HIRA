"""Sprint 65 PR 1 — InstagramProvider foundation checks.

No database, no HTTP, no Meta calls anywhere in this file — matching
`tests/test_whatsapp_provider.py`'s DB-free contract. Covers what's
genuinely implemented (capabilities, routing key, signature verification,
subscription handshake, best-effort payload parsing) and asserts the
documented placeholders (`validate_credentials`, `send`) raise
`NotImplementedError` rather than silently returning fabricated success/
failure — see `provider.py`'s module docstring for why that split exists.
"""

from __future__ import annotations

import hashlib
import hmac
import json

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


def test_capabilities_are_empty(provider):
    """Deliberately empty — see capabilities()'s own docstring. Not a
    platform limitation; a statement that nothing is implemented
    end-to-end yet (send() is NotImplementedError)."""
    caps = provider.capabilities()
    assert caps.channel == "instagram"
    for capability in Capability:
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


def test_send_raises_not_implemented(provider):
    message = OutboundMessage(channel="instagram", external_conversation_id="IGSID_1", text="hi")
    creds = ChannelCredentials(
        channel="instagram", access_token="tok", external_account_id="IG_ACCT_1"
    )
    with pytest.raises(NotImplementedError):
        provider.send(message, creds)
