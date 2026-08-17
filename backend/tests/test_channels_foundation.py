"""Sprint 64A PR 2 — foundation-only checks.

No database is used anywhere in this file: everything under app.channels
and the two new service skeletons is deliberately DB-free, so these tests
run without the postgres fixture other suites need.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.channels.base.capabilities import Capability, CapabilitySet
from app.channels.base.credentials import ChannelCredentials
from app.channels.base.errors import (
    CapabilityNotSupportedError,
    ProviderNotFoundError,
)
from app.channels.base.message import NormalizedMessage, OutboundMessage
from app.channels.base.provider import ChannelProvider
from app.channels.base.results import ConnectionResult, DeliveryReceipt
from app.channels.registry import ChannelRegistry
from app.services.channel_manager import ChannelManager
from app.services.messaging_service import MessagingService


class FakeProvider(ChannelProvider):
    """Minimal concrete provider, used only to exercise the abstraction —
    never registered against production's default registry."""

    channel_id = "fake"

    def capabilities(self) -> CapabilitySet:
        return CapabilitySet(channel=self.channel_id, supported=frozenset({Capability.TEXT}))

    def validate_credentials(self, creds: ChannelCredentials) -> ConnectionResult:
        return ConnectionResult(success=True, external_account_id="acct-1")

    def extract_routing_key(self, raw_body: bytes) -> str:
        return "acct-1"

    def verify_webhook_signature(self, headers, raw_body, creds) -> bool:
        return True

    def verify_subscription(self, query_params, creds) -> str | None:
        return query_params.get("challenge")

    def parse_webhook(self, raw_body: bytes) -> list[NormalizedMessage]:
        return [
            NormalizedMessage(
                channel=self.channel_id,
                external_conversation_id="conv-1",
                external_message_id="msg-1",
                external_sender_id="sender-1",
                text="hello",
            )
        ]

    def send(self, message: OutboundMessage, creds: ChannelCredentials) -> DeliveryReceipt:
        return DeliveryReceipt(status="sent", external_message_id="sent-1")


# --- ChannelProvider is a real ABC -----------------------------------------


def test_channel_provider_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        ChannelProvider()  # type: ignore[abstract]


# --- DTOs are immutable and channel-neutral --------------------------------


def test_normalized_message_is_frozen():
    message = NormalizedMessage(
        channel="fake",
        external_conversation_id="c1",
        external_message_id="m1",
        external_sender_id="s1",
        text="hi",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        message.text = "changed"  # type: ignore[misc]


# --- CapabilitySet -----------------------------------------------------


def test_capability_set_supports():
    caps = CapabilitySet(channel="fake", supported=frozenset({Capability.TEXT}))
    assert caps.supports(Capability.TEXT) is True
    assert caps.supports(Capability.VIDEO) is False


# --- ChannelRegistry ------------------------------------------------------


def test_registry_register_and_get():
    registry = ChannelRegistry()
    provider = FakeProvider()
    registry.register(provider)
    assert registry.get("fake") is provider
    assert registry.available() == ("fake",)


def test_registry_unknown_channel_raises():
    registry = ChannelRegistry()
    with pytest.raises(ProviderNotFoundError, match="No provider registered"):
        registry.get("nonexistent")


def test_registry_instances_do_not_share_state():
    a, b = ChannelRegistry(), ChannelRegistry()
    a.register(FakeProvider())
    assert a.available() == ("fake",)
    assert b.available() == ()


# --- ChannelManager (resolve + capability validation only) ----------------


def test_channel_manager_resolves_via_its_registry():
    registry = ChannelRegistry()
    provider = FakeProvider()
    registry.register(provider)
    manager = ChannelManager(registry=registry)
    assert manager.resolve("fake") is provider


def test_channel_manager_validates_supported_capability():
    registry = ChannelRegistry()
    registry.register(FakeProvider())
    manager = ChannelManager(registry=registry)
    manager.validate_capability("fake", Capability.TEXT)  # does not raise


def test_channel_manager_rejects_unsupported_capability():
    registry = ChannelRegistry()
    registry.register(FakeProvider())
    manager = ChannelManager(registry=registry)
    with pytest.raises(CapabilityNotSupportedError, match="does not support 'video'"):
        manager.validate_capability("fake", Capability.VIDEO)


def test_channel_manager_send_not_implemented_yet():
    manager = ChannelManager(registry=ChannelRegistry())
    with pytest.raises(NotImplementedError):
        manager.send(
            OutboundMessage(channel="fake", external_conversation_id="c1", text="hi"),
            ChannelCredentials(channel="fake", access_token="token"),
        )


def test_channel_manager_handle_inbound_not_implemented_yet():
    manager = ChannelManager(registry=ChannelRegistry())
    with pytest.raises(NotImplementedError):
        manager.handle_inbound("fake", b"{}", {})


# --- MessagingService (skeleton only) --------------------------------------


def test_messaging_service_methods_not_implemented_yet():
    service = MessagingService(db=None)  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        service.record_inbound(business_id=None, messages=[])  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        service.send_reply(conversation_id=None, text="hi")  # type: ignore[arg-type]
    with pytest.raises(NotImplementedError):
        service.approve_and_send(message_id=None)  # type: ignore[arg-type]
