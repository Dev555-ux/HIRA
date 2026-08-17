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

`parse_inbound_payload`/`_extract_text` intentionally mirror (not reuse)
`app/webhooks/whatsapp.py::_persist_inbound`'s parsing logic — the
production webhook route keeps using its own inline parsing for the actual
commit path; this is a deliberate, temporary duplication covered by tests
asserting identical output for the same input, so the two can't drift
without a test failing. See app/channels/whatsapp/shadow.py (PR 4), which
exists specifically to catch drift on live traffic beyond what synthetic
test fixtures cover.

`signature_valid`, unlike the above, is not a mirror — it's the single
real implementation, moved here from `webhooks/whatsapp.py` in PR 4 so both
`WhatsAppProvider.verify_webhook_signature()` and the production webhook
route import the same function instead of one depending on the other
(importing it the other way around, from webhooks/whatsapp.py, creates a
circular import once webhooks/whatsapp.py itself needs to import from
app.channels.whatsapp for Shadow Mode). Behavior is unchanged — same HMAC-
SHA256 comparison, same "sha256=" prefix handling — only its location and,
since nothing outside this package needs it to be a "private" underscored
name anymore, its name.

Future integration point: `WhatsAppProvider.parse_webhook()` (provider.py)
calls `parse_inbound_payload()` after decoding the raw body as JSON.
"""

from __future__ import annotations

import hashlib
import hmac

from app.channels.base.message import NormalizedMessage

CHANNEL_ID = "whatsapp"


def signature_valid(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    """True only if `header` is a valid `X-Hub-Signature-256` HMAC-SHA256
    of `raw_body` under `app_secret` — Meta's webhook signing scheme."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


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
