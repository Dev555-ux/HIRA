"""Sprint 64A PR 6 — ChannelManager as the production outbound router.

No database anywhere in this file: `ChannelManager.send()` is DB-free by
contract (it receives `ChannelCredentials` as a parameter, never fetches
them), so these tests run without the postgres fixture other suites need.
Uses a configurable `ScriptedProvider` fake rather than `WhatsAppProvider`
directly — retry/capability/error-normalization behavior belongs to
`ChannelManager` regardless of which provider is behind it, and a fake
that can be told exactly what to return on each call makes the retry-
exhaustion and retry-then-succeed cases trivial to set up precisely.
`WhatsAppProvider`-specific retryable/non-retryable classification (which
Graph API status maps to which) is covered separately in
tests/test_whatsapp_provider.py and tests/test_messaging.py.
"""

from __future__ import annotations

import pytest

from app.channels.base.capabilities import Capability, CapabilitySet
from app.channels.base.credentials import ChannelCredentials
from app.channels.base.errors import CapabilityNotSupportedError, ProviderNotFoundError
from app.channels.base.message import OutboundMessage
from app.channels.base.provider import ChannelProvider
from app.channels.base.results import ConnectionResult, DeliveryReceipt
from app.channels.registry import ChannelRegistry
from app.services.channel_manager import ChannelManager

MESSAGE = OutboundMessage(channel="fake", external_conversation_id="+15551230000", text="hi")
CREDS = ChannelCredentials(channel="fake", access_token="token")


class ScriptedProvider(ChannelProvider):
    """A provider whose `send()` returns a pre-scripted sequence of
    receipts (or raises a pre-scripted exception) — one entry consumed per
    call, so a test can assert exactly how many attempts ChannelManager
    made."""

    channel_id = "fake"

    def __init__(self, capabilities: frozenset[Capability] = frozenset({Capability.TEXT})):
        self._capabilities = capabilities
        self.script: list[DeliveryReceipt | Exception] = []
        self.calls = 0

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(channel=self.channel_id, supported=self._capabilities)

    def validate_credentials(self, creds: ChannelCredentials) -> ConnectionResult:
        raise NotImplementedError

    def extract_routing_key(self, raw_body: bytes) -> str:
        raise NotImplementedError

    def verify_webhook_signature(self, headers, raw_body, creds) -> bool:
        raise NotImplementedError

    def verify_subscription(self, query_params, creds):
        raise NotImplementedError

    def parse_webhook(self, raw_body: bytes) -> list:
        raise NotImplementedError

    def send(self, message: OutboundMessage, creds: ChannelCredentials) -> DeliveryReceipt:
        self.calls += 1
        outcome = self.script[self.calls - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _manager(provider: ScriptedProvider, *, max_attempts: int = 3) -> ChannelManager:
    registry = ChannelRegistry()
    registry.register(provider)
    return ChannelManager(registry=registry, max_attempts=max_attempts)


# --- provider resolution -----------------------------------------------


def test_resolves_provider_through_the_registry():
    provider = ScriptedProvider()
    manager = _manager(provider)
    assert manager.resolve("fake") is provider


def test_missing_provider_raises_provider_not_found():
    manager = ChannelManager(registry=ChannelRegistry())
    with pytest.raises(ProviderNotFoundError):
        manager.send(MESSAGE, CREDS)


# --- successful routing ---------------------------------------------------


def test_successful_send_routes_through_provider_exactly_once():
    provider = ScriptedProvider()
    provider.script = [DeliveryReceipt(status="sent", external_message_id="msg-1")]
    manager = _manager(provider)

    receipt = manager.send(MESSAGE, CREDS)

    assert receipt.status == "sent"
    assert receipt.external_message_id == "msg-1"
    assert provider.calls == 1


# --- capability validation --------------------------------------------------


def test_capability_failure_raises_before_calling_the_provider():
    provider = ScriptedProvider(capabilities=frozenset())  # supports nothing
    provider.script = [DeliveryReceipt(status="sent", external_message_id="unreachable")]
    manager = _manager(provider)

    with pytest.raises(CapabilityNotSupportedError, match="does not support 'text'"):
        manager.send(MESSAGE, CREDS)

    assert provider.calls == 0  # never reached the transport


# --- retry: success after transient failures --------------------------


def test_retries_a_retryable_failure_then_succeeds(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("app.services.channel_manager.time.sleep", lambda s: sleeps.append(s))

    provider = ScriptedProvider()
    provider.script = [
        DeliveryReceipt(status="failed", retryable=True, error="503"),
        DeliveryReceipt(status="failed", retryable=True, error="503"),
        DeliveryReceipt(status="sent", external_message_id="msg-3"),
    ]
    manager = _manager(provider)

    receipt = manager.send(MESSAGE, CREDS)

    assert receipt.status == "sent"
    assert receipt.external_message_id == "msg-3"
    assert provider.calls == 3
    # Same backoff curve as send_text: 0.2 * attempt for each retry taken.
    assert sleeps == [0.2, 0.4]


# --- retry exhaustion -------------------------------------------------------


def test_retry_exhaustion_returns_the_last_failed_receipt(monkeypatch):
    monkeypatch.setattr("app.services.channel_manager.time.sleep", lambda s: None)

    provider = ScriptedProvider()
    provider.script = [
        DeliveryReceipt(status="failed", retryable=True, error="attempt 1"),
        DeliveryReceipt(status="failed", retryable=True, error="attempt 2"),
        DeliveryReceipt(status="failed", retryable=True, error="attempt 3"),
    ]
    manager = _manager(provider)

    receipt = manager.send(MESSAGE, CREDS)

    assert receipt.status == "failed"
    assert receipt.error == "attempt 3"  # the last attempt's own failure, not a synthesized one
    assert provider.calls == 3  # exactly max_attempts, no fourth try


def test_non_retryable_failure_stops_immediately_without_exhausting_attempts():
    provider = ScriptedProvider()
    provider.script = [DeliveryReceipt(status="failed", retryable=False, error="bad request")]
    manager = _manager(provider)

    receipt = manager.send(MESSAGE, CREDS)

    assert receipt.status == "failed"
    assert receipt.error == "bad request"
    assert provider.calls == 1  # never retried


# --- provider exception -----------------------------------------------


def test_provider_exception_is_normalized_to_a_failed_receipt_without_retrying():
    provider = ScriptedProvider()
    provider.script = [RuntimeError("provider bug")]
    manager = _manager(provider)

    receipt = manager.send(MESSAGE, CREDS)

    assert receipt.status == "failed"
    assert receipt.retryable is False
    assert "provider bug" in receipt.error
    assert provider.calls == 1  # unexpected exceptions are not retried


# --- delivery receipt propagation --------------------------------------


def test_successful_receipts_raw_field_propagates_unmodified():
    provider = ScriptedProvider()
    provider.script = [
        DeliveryReceipt(status="sent", external_message_id="msg-1", raw={"meta": "value"})
    ]
    manager = _manager(provider)

    receipt = manager.send(MESSAGE, CREDS)

    assert receipt.raw == {"meta": "value"}
