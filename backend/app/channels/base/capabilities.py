"""What a channel can and can't do, as data instead of code.

Purpose: let ChannelManager and (eventually) MessagingService ask "can this
channel do X?" and get a straight answer, instead of encoding per-channel
knowledge as `if channel == "whatsapp"` conditionals scattered through the
codebase. This is the mechanism that lets a new provider slot in without
any existing caller changing — see the Sprint 64A architecture doc's
future-proofing section.

Responsibilities: `Capability` names the things a channel might support.
`CapabilitySet` is what a provider declares it actually supports, with one
cheap membership check.

Does NOT do: enforce anything by itself — a provider can still be called
for an unsupported capability unless something upstream checks first. That
check is `ChannelManager.validate_capability()` (channel_manager.py), not
this module; this module only holds the data.

Future integration point: `ChannelProvider.capabilities()` returns a
`CapabilitySet`; `ChannelManager` calls `.supports()` on it before invoking
`send()` for anything beyond plain text.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Capability(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    DOCUMENT = "document"
    AUDIO = "audio"
    REACTIONS = "reactions"
    TYPING = "typing"
    TEMPLATES = "templates"
    STORY_REPLY = "story_reply"
    READ_RECEIPTS = "read_receipts"
    DELIVERY_RECEIPTS = "delivery_receipts"


@dataclass(frozen=True)
class CapabilitySet:
    """`channel` is carried alongside `supported` purely so a `CapabilitySet`
    is self-describing in logs/errors — it plays no role in the membership
    check itself."""

    channel: str
    supported: frozenset[Capability]

    def supports(self, capability: Capability) -> bool:
        return capability in self.supported
