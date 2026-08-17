"""Sprint 64A PR 3 — WhatsAppProvider foundation checks.

No database anywhere in this file: `WhatsAppProvider` is DB-free by
contract, so these tests run without the postgres fixture other suites
need. Neither `extract_routing_key` nor `_extract_text` are checked for
parity against a second, separate implementation here anymore — both
retired in Sprint 64A (PR 5 for message parsing, PR 7 for routing-key
extraction, when `app/webhooks/whatsapp.py::_first_phone_number_id` was
removed in favor of calling this provider directly): production has
exactly one implementation of each, and this file tests it directly
(see tests/test_whatsapp_cutover.py for the webhook-level integration
tests).
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
from app.channels.whatsapp.parsing import _extract_text, parse_inbound_payload, signature_valid
from app.channels.whatsapp.provider import WhatsAppProvider
from app.core.config import settings

APP_SECRET = "test-app-secret"


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _sign(body: bytes, secret: str = APP_SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _inbound_payload(phone_number_id="PN1", wa_message_id="wamid.1", from_phone="+15551230000"):
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [{"wa_id": from_phone, "profile": {"name": "Test User"}}],
                            "messages": [
                                {
                                    "id": wa_message_id,
                                    "from": from_phone,
                                    "type": "text",
                                    "text": {"body": "Hi, are you open today?"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


@pytest.fixture
def provider() -> WhatsAppProvider:
    return WhatsAppProvider()


# --- construction & capabilities -------------------------------------------


def test_provider_channel_id():
    assert WhatsAppProvider().channel_id == "whatsapp"


def test_capabilities_only_text(provider):
    caps = provider.capabilities()
    assert caps.channel == "whatsapp"
    assert caps.supports(Capability.TEXT) is True
    for capability in Capability:
        if capability is Capability.TEXT:
            continue
        assert caps.supports(capability) is False, f"{capability} should not be advertised yet"


# --- routing key -------------------------------------------------------


def test_extract_routing_key_returns_the_phone_number_id(provider):
    payload = _inbound_payload(phone_number_id="PN42")
    raw_body = json.dumps(payload).encode()

    assert provider.extract_routing_key(raw_body) == "PN42"


def test_extract_routing_key_malformed_json_raises(provider):
    with pytest.raises(WebhookVerificationFailedError):
        provider.extract_routing_key(b"not json")


def test_extract_routing_key_missing_phone_number_id_raises(provider):
    with pytest.raises(WebhookVerificationFailedError):
        provider.extract_routing_key(b"{}")


# --- webhook signature, checked for parity against the production helper --


def test_verify_webhook_signature_valid_matches_production_helper(provider):
    raw_body = json.dumps(_inbound_payload()).encode()
    header = _sign(raw_body)
    creds = ChannelCredentials(channel="whatsapp", access_token="tok", secret=APP_SECRET)

    assert (
        provider.verify_webhook_signature({"X-Hub-Signature-256": header}, raw_body, creds)
        is signature_valid(raw_body, header, APP_SECRET)
        is True
    )


def test_verify_webhook_signature_wrong_secret_rejected(provider):
    raw_body = json.dumps(_inbound_payload()).encode()
    header = _sign(raw_body, secret="wrong-secret")
    creds = ChannelCredentials(channel="whatsapp", access_token="tok", secret=APP_SECRET)

    assert (
        provider.verify_webhook_signature({"X-Hub-Signature-256": header}, raw_body, creds) is False
    )


def test_verify_webhook_signature_no_secret_on_credentials_rejected(provider):
    raw_body = json.dumps(_inbound_payload()).encode()
    header = _sign(raw_body)
    creds = ChannelCredentials(channel="whatsapp", access_token="tok", secret=None)

    assert (
        provider.verify_webhook_signature({"X-Hub-Signature-256": header}, raw_body, creds) is False
    )


# --- subscription handshake -------------------------------------------------


def test_verify_subscription_echoes_challenge_on_match(provider, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_verify_token", "shared-verify-token")
    creds = ChannelCredentials(channel="whatsapp", access_token="unused")

    result = provider.verify_subscription(
        {
            "hub.mode": "subscribe",
            "hub.verify_token": "shared-verify-token",
            "hub.challenge": "123",
        },
        creds,
    )

    assert result == "123"


def test_verify_subscription_wrong_token_returns_none(provider, monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_verify_token", "shared-verify-token")
    creds = ChannelCredentials(channel="whatsapp", access_token="unused")

    result = provider.verify_subscription(
        {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "123"}, creds
    )

    assert result is None


# --- payload normalization ---------------------------------------------


def test_extract_text_reads_text_message_body():
    msg = {"type": "text", "text": {"body": "hello"}}
    assert _extract_text(msg) == "hello"


@pytest.mark.parametrize(
    "msg",
    [
        {"type": "image", "image": {"id": "media-1"}},
        {"type": "interactive"},
        {},
    ],
)
def test_extract_text_returns_empty_string_for_non_text_messages(msg):
    assert _extract_text(msg) == ""


def test_parse_webhook_normalizes_a_text_message(provider):
    payload = _inbound_payload(wa_message_id="wamid.7", from_phone="+15559998888")
    messages = provider.parse_webhook(json.dumps(payload).encode())

    assert len(messages) == 1
    message = messages[0]
    assert message.channel == "whatsapp"
    assert message.external_conversation_id == "+15559998888"
    assert message.external_sender_id == "+15559998888"
    assert message.external_message_id == "wamid.7"
    assert message.sender_display_name == "Test User"
    assert message.text == "Hi, are you open today?"
    assert message.media == ()


def test_parse_inbound_payload_skips_status_callbacks():
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "PN1"},
                            "statuses": [{"id": "wamid.1", "status": "delivered"}],
                        }
                    }
                ]
            }
        ]
    }
    assert parse_inbound_payload(payload) == []


def test_parse_webhook_malformed_json_raises(provider):
    with pytest.raises(WebhookVerificationFailedError):
        provider.parse_webhook(b"not json")


# --- credential validation --------------------------------------------------
#
# validate_credentials() calls verify_whatsapp_credentials() without a client
# override (matching that function's own real call signature — no `client`
# param is threaded through ChannelProvider's interface), so success/failure
# paths here are exercised by monkeypatching the imported symbol rather than
# a real HTTP call. The live Graph API call itself is already covered by
# tests/test_whatsapp_credentials.py — this file only tests the DTO
# translation layer WhatsAppProvider adds on top of it.


def test_validate_credentials_missing_external_account_id(provider):
    creds = ChannelCredentials(channel="whatsapp", access_token="tok", external_account_id=None)

    result = provider.validate_credentials(creds)

    assert result.success is False
    assert "external_account_id" in result.error


def test_validate_credentials_success(provider, monkeypatch):
    import app.channels.whatsapp.provider as provider_module

    monkeypatch.setattr(
        provider_module,
        "verify_whatsapp_credentials",
        lambda phone_number_id, access_token: "+1 555 000 0000",
    )
    creds = ChannelCredentials(channel="whatsapp", access_token="tok", external_account_id="PN1")

    result = provider.validate_credentials(creds)

    assert result.success is True
    assert result.external_account_id == "PN1"
    assert result.display_name == "+1 555 000 0000"


def test_validate_credentials_invalid_credential_returns_failure(provider, monkeypatch):
    import app.channels.whatsapp.provider as provider_module
    from app.whatsapp.errors import WhatsAppCredentialInvalidError

    def raise_invalid(phone_number_id, access_token):
        raise WhatsAppCredentialInvalidError("Meta rejected the access token")

    monkeypatch.setattr(provider_module, "verify_whatsapp_credentials", raise_invalid)
    creds = ChannelCredentials(channel="whatsapp", access_token="bad", external_account_id="PN1")

    result = provider.validate_credentials(creds)

    assert result.success is False
    assert result.error == "Meta rejected the access token"


# --- outbound send, against a mocked Graph API ------------------------------


def test_send_success_returns_delivery_receipt():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer good-token"
        return httpx.Response(200, json={"messages": [{"id": "wamid.sent-1"}]})

    from app.channels.whatsapp.send import send_whatsapp_message

    message = OutboundMessage(
        channel="whatsapp", external_conversation_id="+15551230000", text="hi"
    )
    creds = ChannelCredentials(
        channel="whatsapp", access_token="good-token", external_account_id="PN1"
    )

    receipt = send_whatsapp_message(message, creds, client=_client(handler))

    assert receipt.status == "sent"
    assert receipt.external_message_id == "wamid.sent-1"


def test_send_failure_returns_failed_delivery_receipt():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="bad request")

    from app.channels.whatsapp.send import send_whatsapp_message

    message = OutboundMessage(
        channel="whatsapp", external_conversation_id="+15551230000", text="hi"
    )
    creds = ChannelCredentials(
        channel="whatsapp", access_token="good-token", external_account_id="PN1"
    )

    receipt = send_whatsapp_message(message, creds, client=_client(handler))

    assert receipt.status == "failed"
    assert receipt.error is not None


def test_send_missing_external_account_id_fails_without_calling_out():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("should not make an HTTP call without a phone_number_id")

    from app.channels.whatsapp.send import send_whatsapp_message

    message = OutboundMessage(
        channel="whatsapp", external_conversation_id="+15551230000", text="hi"
    )
    creds = ChannelCredentials(
        channel="whatsapp", access_token="good-token", external_account_id=None
    )

    receipt = send_whatsapp_message(message, creds, client=_client(handler))

    assert receipt.status == "failed"
    assert "external_account_id" in receipt.error
