"""Meta Cloud API webhook payload -> NormalizedMessage. Pure translation only.

Purpose: the one place Meta's `entry -> changes -> value -> messages` JSON
shape gets read, so nothing else in the codebase has to know that shape.

Responsibilities: walk the payload, skip delivery/status callbacks (they
carry "statuses", not "messages" — HIRA doesn't process those today), and
produce one `NormalizedMessage` per inbound message.

Does NOT do: persistence, deduplication, job enqueueing, or Customer/
Conversation resolution — those are MessagingService's job once it exists.
This module has no database import and no side effects; it is a pure
function of its input.

This intentionally mirrors (not reuses) `app/webhooks/whatsapp.py`'s
`_persist_inbound`/`_extract_text` parsing logic. PR 3 does not touch
`webhooks/whatsapp.py` — the production webhook route keeps using its own
inline parsing until the PR that cuts it over to call this module through
ChannelManager. Until that cutover, this is a deliberate, temporary
duplication of the parsing logic (not the persistence logic, which stays
exclusively in webhooks/whatsapp.py): both implementations are covered by
tests asserting identical output for the same input, so the two can't drift
without a test failing.

Future integration point: `WhatsAppProvider.parse_webhook()` (provider.py)
calls `parse_inbound_payload()` after decoding the raw body as JSON.
"""

from __future__ import annotations

from app.channels.base.message import NormalizedMessage

CHANNEL_ID = "whatsapp"


def parse_inbound_payload(payload: dict) -> list[NormalizedMessage]:
    """Same traversal as `_persist_inbound`'s outer two loops, minus every
    database call. `external_conversation_id` and `external_sender_id` are
    both the customer's WhatsApp phone number (`wa_id`/`from`) — WhatsApp
    has no separate per-thread id, so the phone number *is* the thread
    identity, matched to a HIRA `Conversation` downstream."""
    messages: list[NormalizedMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if not value.get("messages"):
                continue  # delivery/status callback, not a message

            names = {
                contact.get("wa_id"): contact.get("profile", {}).get("name")
                for contact in value.get("contacts", [])
            }
            for msg in value.get("messages", []):
                wa_phone = msg.get("from", "")
                messages.append(
                    NormalizedMessage(
                        channel=CHANNEL_ID,
                        external_conversation_id=wa_phone,
                        external_message_id=msg.get("id", ""),
                        external_sender_id=wa_phone,
                        sender_display_name=names.get(wa_phone),
                        text=_extract_text(msg),
                        raw=msg,
                    )
                )
    return messages


def _extract_text(msg: dict) -> str:
    """Identical to `app/webhooks/whatsapp.py::_extract_text` — only
    `type == "text"` messages carry a body today; every other type (image,
    audio, interactive, template, ...) normalizes to an empty string, same
    as production does now. Not a gap introduced by this PR."""
    if msg.get("type") == "text":
        return msg.get("text", {}).get("body", "")
    return ""
