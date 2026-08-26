"""Transport-level message DTOs every ChannelProvider speaks in.

Purpose: give providers and callers a shared, channel-neutral shape for a
message, so `app.ai.orchestrator` and (eventually) `MessagingService` never
have to know whether a message came from Meta's webhook JSON, Instagram's
Graph API shape, or anything else. A provider's whole job is translating
its native payload into `NormalizedMessage` and translating an
`OutboundMessage` back into its native API call — nothing upstream of a
provider should ever touch a native payload directly.

What these deliberately do NOT do: carry a database id, an ORM relationship,
or any HIRA-internal concept (Business, Conversation, Customer). They only
know about the *external* world — provider-native ids and raw content. The
first place a `NormalizedMessage` gets mapped onto internal rows is the
(not-yet-built) MessagingService, not here.

Future integration point: `ChannelProvider.parse_webhook()` returns
`list[NormalizedMessage]`; `ChannelProvider.send()` takes an
`OutboundMessage`. Both are defined in provider.py.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum


class MediaKind(str, Enum):
    """What kind of attachment a MediaRef points to. Deliberately a small,
    generic set — a provider that receives something it can't classify
    should map it to DOCUMENT rather than growing this enum per-channel."""

    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"


@dataclass(frozen=True)
class MediaRef:
    """A pointer to one piece of media, inbound or outbound.

    `url` is provider-native (e.g. a Meta media-download URL that expires,
    or a caller-supplied URL for outbound) — HIRA's own media storage, if
    any, is a MessagingService concern, not a transport concern.
    """

    kind: MediaKind
    url: str
    mime_type: str | None = None
    caption: str | None = None


@dataclass(frozen=True)
class NormalizedMessage:
    """One inbound message, already translated out of a provider's native
    payload shape.

    Purpose: the single shape every `ChannelProvider.parse_webhook()`
    implementation must produce, regardless of channel.

    Responsibilities: carry exactly what's needed to persist a message and
    resolve who sent it — nothing more.

    Does NOT do: identify a HIRA `Business`/`Customer`/`Conversation` (that
    resolution — matching `external_conversation_id` to internal rows — is
    MessagingService's job); does not carry retry state or delivery status
    (that's DeliveryReceipt, for the outbound direction).

    Future integration point: returned by `ChannelProvider.parse_webhook()`;
    consumed by the not-yet-built MessagingService, which resolves/creates
    the matching Business/Customer/Conversation and enqueues the AI job.
    """

    channel: str
    external_conversation_id: str
    external_message_id: str
    external_sender_id: str
    text: str
    sender_display_name: str | None = None
    media: tuple[MediaRef, ...] = ()
    # Ad-click id, when this message is the one that opened an ad-originated
    # thread (Sprint 73). WhatsApp calls it `referral.ctwa_clid`; a provider
    # that has no such concept simply leaves it None. Carried on the DTO
    # rather than read out of `.raw` downstream for the same reason
    # external_message_id is (see MessagingService.record_inbound's comment):
    # `.raw` key names are channel-native and silently return None on any
    # channel that doesn't share WhatsApp's payload shape.
    ctwa_clid: str | None = None
    raw: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class OutboundMessage:
    """One message HIRA wants to send, before a provider translates it into
    a native API call.

    Purpose: the single shape every `ChannelProvider.send()` implementation
    must accept, regardless of channel.

    Does NOT do: know which business or credential is sending it (that's
    `ChannelCredentials`, passed alongside this to `send()`); know how many
    times to retry on failure (that's ChannelManager's job, not the
    provider's — see channel_manager.py).

    Future integration point: constructed by MessagingService from an AI
    reply or a human-approved draft; passed to `ChannelManager.send()`,
    which resolves a provider and calls `ChannelProvider.send()`.
    """

    channel: str
    external_conversation_id: str
    text: str
    media: tuple[MediaRef, ...] = ()
    reply_to_external_id: str | None = None
