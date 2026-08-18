"""Instagram webhook payload -> NormalizedMessage. Pure translation only.

Purpose: the one place Instagram's Messenger-Platform-shaped webhook JSON
gets read, so nothing else in the codebase has to know that shape.

Payload shape assumption (Meta's documented Instagram Messaging webhook
format at the time of writing — this has not been tested against a live
Instagram account; re-verify against Meta's current docs before Sprint 65
PR 5 wires this up for real):

    {
        "object": "instagram",
        "entry": [
            {
                "id": "<instagram_business_account_id>",
                "time": 1700000000,
                "messaging": [
                    {
                        "sender": {"id": "<IGSID>"},
                        "recipient": {"id": "<instagram_business_account_id>"},
                        "timestamp": 1700000000,
                        "message": {"mid": "<message_id>", "text": "..."}
                    }
                ]
            }
        ]
    }

This is the Messenger Platform's webhook envelope (`entry[].messaging[]`,
`sender`/`recipient`/`message`), which Instagram Messaging reuses — a
structurally different shape from WhatsApp Cloud API's `entry[].changes[]
.value.messages[]`, not a variant of it. `signature_valid()` below is the
one exception: Meta uses the identical X-Hub-Signature-256 HMAC-SHA256
scheme across every webhook product (WhatsApp, Messenger, Instagram), so
this is the same algorithm as `app.channels.whatsapp.parsing.
signature_valid()`, deliberately re-implemented here rather than imported
from it — providers are self-contained packages (see
documentation/architecture/channel-development-guide.md); Instagram
support must not depend on WhatsApp's package existing.

Known unsupported payload shapes (Sprint 65 PR 1 scope; PR 6 adds
`attachments`, see below): Instagram messaging events this module
recognizes as "a message exists" but does not extract meaningful content
from — each normalizes to an empty `text`/`media`, the same
"unsupported -> empty, not fatal" convention
`app.channels.whatsapp.parsing._extract_text()` established, not a gap
introduced here:

- `is_deleted` — a message-deletion notification, not new content.
- `reactions` — a reaction added to a previous message.
- `read` — a read-receipt event, not a message.
- `story_mention` / a reply to a Story — arrives as an `attachments`
  entry whose `type` is `"story_mention"`, not one of the four kinds
  `_extract_media()` below maps (image/video/audio/file) — recognized as
  "a message" but its attachment is dropped, same as any other unknown
  attachment type (see `_extract_media()`).

None of these raise — only genuinely malformed input (not valid JSON, or
missing the fields routing depends on) does.

Media (Sprint 65 PR 6): `attachments` (image/video/audio/file — Meta's
Instagram Messaging webhook reuses the Messenger Platform's
`message.attachments[].{type,payload.url}` shape) now maps onto
`NormalizedMessage.media`. An attachment whose `type` isn't one of those
four (a share, a story_mention, or anything Meta adds later) is dropped
silently — never raises, matching this module's existing
"unsupported -> empty" convention rather than the "empty text" special
case above.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from app.channels.base.message import MediaKind, MediaRef, NormalizedMessage

CHANNEL_ID = "instagram"

logger = logging.getLogger(__name__)

# Meta's inbound attachment `type` string -> our channel-neutral MediaKind.
# Anything else (e.g. "share", "story_mention", "template", "fallback") is
# not one of the four kinds this platform models — dropped, not mapped.
_ATTACHMENT_KIND = {
    "image": MediaKind.IMAGE,
    "video": MediaKind.VIDEO,
    "audio": MediaKind.AUDIO,
    "file": MediaKind.DOCUMENT,
}


def signature_valid(raw_body: bytes, header: str | None, app_secret: str) -> bool:
    """True only if `header` is a valid `X-Hub-Signature-256` HMAC-SHA256
    of `raw_body` under `app_secret` — identical scheme to WhatsApp's
    `signature_valid()` (Meta's webhook signing convention is shared
    across products); see module docstring for why this is a separate,
    self-contained copy rather than a shared import."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


def first_business_account_id(payload: dict) -> str | None:
    """A single webhook delivery covers one subscribed Instagram Business
    Account per `entry` — reading the first `entry[].id` found is enough
    to know which business's secret to verify against, same one-business-
    per-delivery assumption `app.channels.whatsapp.parsing`'s routing-key
    extraction makes for WhatsApp."""
    for entry in payload.get("entry", []):
        account_id = entry.get("id")
        if account_id:
            return account_id
    return None


def parse_messaging_events(messaging_events: list[dict]) -> list[NormalizedMessage]:
    """Translates one `entry[].messaging` array into `NormalizedMessage`s.

    Only genuine message events (a `message` key present) are turned into
    a `NormalizedMessage` — `read`/reaction-only events (no `message` key)
    are skipped entirely, mirroring how `app.channels.whatsapp.parsing.
    parse_inbound_payload()` skips delivery/status-only Meta "changes".
    `external_conversation_id`/`external_sender_id` are both the sender's
    IGSID — Instagram, like WhatsApp, has no separate per-thread id
    distinct from the participant.

    Does NOT do: fetch the sender's username/display name. Unlike
    WhatsApp's webhook (which inlines `contacts[].profile.name`),
    Instagram's messaging webhook carries no profile information at all —
    getting one requires a separate `GET /{IGSID}` Graph API call, itself
    gated by Meta's messaging-window policies. `sender_display_name` is
    always `None` here; resolving it, if ever needed, is a live-API
    concern for a later PR, not something this pure function can do.
    """
    messages: list[NormalizedMessage] = []
    for event in messaging_events:
        message = event.get("message")
        if message is None:
            # A read receipt, reaction, or any other non-message event —
            # never crash because Meta adds a new event type; debug-only
            # since this isn't an error, just something this provider
            # doesn't turn into a NormalizedMessage yet.
            logger.debug("Skipping non-message Instagram messaging event: %s", sorted(event.keys()))
            continue

        sender_id = event.get("sender", {}).get("id", "")
        messages.append(
            NormalizedMessage(
                channel=CHANNEL_ID,
                external_conversation_id=sender_id,
                external_message_id=message.get("mid", ""),
                external_sender_id=sender_id,
                sender_display_name=None,
                text=_extract_text(message),
                media=_extract_media(message),
                raw=event,
            )
        )
    return messages


def parse_inbound_payload(payload: dict) -> list[NormalizedMessage]:
    """Whole-payload convenience wrapper over `parse_messaging_events()` —
    walks every `entry`, matching `app.channels.whatsapp.parsing.
    parse_inbound_payload()`'s shape."""
    messages: list[NormalizedMessage] = []
    for entry in payload.get("entry", []):
        messages.extend(parse_messaging_events(entry.get("messaging", [])))
    return messages


def _extract_text(message: dict) -> str:
    """Only a plain `text` field is extracted today; every other shape
    (attachments, story mentions/replies, ...) normalizes to an empty
    string — see module docstring for the full list this deliberately
    does not handle yet."""
    text = message.get("text")
    return text if isinstance(text, str) else ""


def _extract_media(message: dict) -> tuple[MediaRef, ...]:
    """Maps `message.attachments` (a list of `{"type": ..., "payload":
    {"url": ...}}` dicts) onto `MediaRef`s. An entry with an unrecognized
    `type` (see `_ATTACHMENT_KIND`) or missing `payload.url` is skipped,
    not raised on — Meta introducing a new attachment type, or a
    malformed single entry, must never take down inbound parsing for the
    whole message. `caption`/`mime_type` are never present on an inbound
    Instagram attachment (Meta's webhook payload carries neither), so
    both stay `None`."""
    media: list[MediaRef] = []
    attachments = message.get("attachments")
    if not isinstance(attachments, list):
        return ()
    for attachment in attachments:
        if not isinstance(attachment, dict):
            continue
        kind = _ATTACHMENT_KIND.get(attachment.get("type"))
        url = (
            attachment.get("payload", {}).get("url")
            if isinstance(attachment.get("payload"), dict)
            else None
        )
        if kind is None or not url:
            logger.debug("Skipping unsupported Instagram attachment: %s", attachment.get("type"))
            continue
        media.append(MediaRef(kind=kind, url=url))
    return tuple(media)
