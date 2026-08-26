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

`parse_messages` is the single real implementation of Meta message-object ->
`NormalizedMessage` translation (Sprint 64A PR 5 cutover). Two callers, one
implementation:

- `parse_inbound_payload()` below — the whole-payload convenience entrypoint
  `WhatsAppProvider.parse_webhook()` and Shadow Mode use.
- `app/webhooks/whatsapp.py::_persist_inbound()` — calls `parse_messages()`
  directly, per-`change`, rather than `parse_inbound_payload()` on the whole
  payload, because it still needs the per-change `phone_number_id` to
  resolve which `Business` a change belongs to (`NormalizedMessage` has no
  routing/business field — it only carries the *customer's* phone number,
  which is a different thing). That per-change business resolution is
  persistence/routing logic, not message parsing, so it stays in
  `_persist_inbound` unchanged; only the "turn this Meta message dict into a
  DTO" step now runs through this shared function instead of its own
  duplicated inline copy.

Before PR 5, `parse_inbound_payload`/`_extract_text` were a *deliberate,
temporary* mirror of `_persist_inbound`'s then-still-separate inline
parsing, kept honest by parity tests and by Shadow Mode (PR 4) watching live
traffic for drift the synthetic tests didn't cover. That duplication is
gone as of this PR — there is exactly one implementation now.

`signature_valid` is, and always was, the single real implementation,
moved here from `webhooks/whatsapp.py` in PR 4 so both
`WhatsAppProvider.verify_webhook_signature()` and the production webhook
route import the same function instead of one depending on the other.

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


def parse_messages(messages: list[dict], contacts: list[dict]) -> list[NormalizedMessage]:
    """Translates the `messages`/`contacts` arrays from a single Meta
    webhook `change.value` object into `NormalizedMessage`s — the
    per-change granularity `_persist_inbound` needs to preserve its
    existing per-change business resolution. `external_conversation_id`
    and `external_sender_id` are both the customer's WhatsApp phone number
    (`wa_id`/`from`) — WhatsApp has no separate per-thread id, so the phone
    number *is* the thread identity, matched to a HIRA `Conversation`
    downstream.

    `referral.ctwa_clid` (Sprint 73) is Meta's click id for a Click-to-
    WhatsApp ad, present only on the first message of an ad-originated
    thread and absent from every other message — hence `or None`, so an
    empty string from a malformed payload is treated as "no click id"
    rather than a falsy-but-present value the conversions path would then
    have to re-check. The rest of the `referral` object (source_id,
    headline, body, ...) is deliberately not extracted: nothing needs it,
    and it stays available in `.raw` if that changes."""
    names = {contact.get("wa_id"): contact.get("profile", {}).get("name") for contact in contacts}
    return [
        NormalizedMessage(
            channel=CHANNEL_ID,
            external_conversation_id=msg.get("from", ""),
            external_message_id=msg.get("id", ""),
            external_sender_id=msg.get("from", ""),
            sender_display_name=names.get(msg.get("from")),
            text=_extract_text(msg),
            ctwa_clid=msg.get("referral", {}).get("ctwa_clid") or None,
            raw=msg,
        )
        for msg in messages
    ]


def parse_inbound_payload(payload: dict) -> list[NormalizedMessage]:
    """Whole-payload convenience wrapper over `parse_messages()` — walks
    every entry/change, skipping delivery/status callbacks (they carry
    "statuses", not "messages")."""
    messages: list[NormalizedMessage] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            if not value.get("messages"):
                continue  # delivery/status callback, not a message
            messages.extend(parse_messages(value.get("messages", []), value.get("contacts", [])))
    return messages


def _extract_text(msg: dict) -> str:
    """Only `type == "text"` messages carry a body today; every other type
    (image, audio, interactive, template, ...) normalizes to an empty
    string, same as production does now. Not a gap introduced by this PR."""
    if msg.get("type") == "text":
        return msg.get("text", {}).get("body", "")
    return ""
