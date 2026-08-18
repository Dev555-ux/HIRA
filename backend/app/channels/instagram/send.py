"""Outbound send — a single Graph API attempt, DTO-shaped in and out.

Purpose: let `InstagramProvider.send()` accept/return the PR 2 DTOs
without touching the Graph API call itself (mirrors
`app.channels.whatsapp.send`'s shape and division of responsibility).

Endpoint/shape (Sprint 65 PR 5 — corrects PR 1's own docstring, which
assumed `{ig_business_account_id}/messages`; Meta's actual "Instagram API
with Facebook Login" send path is the Messenger Platform's shared Send API,
keyed by the connected **Page**, not the IG business account id):

    POST https://graph.facebook.com/{version}/{page_id}/messages
    Authorization: Bearer {page_access_token}
    {
        "recipient": {"id": "<IGSID>"},
        "message": {"text": "<body>"},
        "messaging_type": "RESPONSE"
    }

    -> 200 {"recipient_id": "<IGSID>", "message_id": "<mid>"}

`messaging_type: "RESPONSE"` is required by Meta's API (a reply within the
24h messaging window — HIRA never sends outside that window; see
`app/services/messaging_service.py`'s window check, which applies
identically to both channels). `creds.external_account_id` must be the
Instagram credential's `page_id` (`InstagramCredential.page_id`,
app/models.py) — never `instagram_business_account_id`, a different Meta
identifier.

Media (Sprint 65 PR 6 — verified against Meta's current Messenger
Platform / Instagram Messaging docs, "Send Messages" and "Attachment
Upload API" pages): a media message replaces `message.text` with
`message.attachment` — Meta does not allow text and an attachment in the
same request, so when `message.media` is non-empty this module builds a
pure attachment payload and drops `message.text` entirely (matches the
platform, not a HIRA-invented restriction):

    {
        "recipient": {"id": "<IGSID>"},
        "message": {
            "attachment": {"type": "image"|"video"|"audio"|"file", "payload": {"url": "<url>"}}
        },
        "messaging_type": "RESPONSE"
    }

`OutboundMessage.media` is a tuple (matching `NormalizedMessage.media`'s
shape for symmetry), but Meta's single-`attachment` object accepts
exactly one URL per request — nothing in this codebase constructs more
than one outbound `MediaRef` per message today, so only `media[0]` is
ever sent; a caller that somehow attaches more gets a logged warning, not
a crash or a silently dropped send. Meta's own multi-image `attachments`
array (up to 10 images, no caption support) is real but unused — there is
no caller in this codebase that needs to send more than one image per
message; add it if one ever does.
`Capability.IMAGE/VIDEO/AUDIO/DOCUMENT` -> `"image"/"video"/"audio"/"file"`
is a closed, total mapping over `MediaKind` (`_ATTACHMENT_TYPE` below) —
every value `InstagramProvider.capabilities()` advertises is backed by a
real mapping here, and the reverse (a `MediaKind` this function can't
map) is handled as a graceful `DeliveryReceipt(status="failed")`, not an
exception, as a defensive backstop in case that invariant is ever broken.
Confirmed file-format/size limits (Meta docs, informational only — not
enforced here, since HIRA never transcodes or re-hosts outbound media,
only passes through a caller-supplied URL): images png/jpeg up to 8MB;
video mp4/ogg/avi/mov/webm and audio aac/m4a/wav/mp4 up to 25MB; files
PDF only, up to 25MB. GIFs are sent as `type: "image"` — Meta has no
separate GIF attachment type.

Retry classification (Sprint 65 PR 5 research — see that PR's own notes
for exact sourcing): Meta error codes 190 (expired/invalid token), 10
(permission error), 100 (malformed request), and the messaging-window-
expired subcode are confidently non-retryable. Codes 4/32 (app/page-level
rate limiting) and any 5xx/network failure are retryable. Everything else
unmapped defaults to non-retryable — retrying an unrecognized failure
blindly risks duplicating a message a customer may have already received,
the same "unexpected -> stop" philosophy WhatsApp's own provider uses
(messaging-platform.md §5). Unchanged for media sends — Graph API error
codes are a platform-wide vocabulary, not endpoint- or payload-specific.

Does NOT retry (ChannelManager's job, §5), does NOT log or return Meta's
raw response body/error message (structured codes only — access tokens
and full Graph error payloads never leave this function).
"""

from __future__ import annotations

import logging

import httpx

from app.channels.base.credentials import ChannelCredentials
from app.channels.base.message import MediaKind, OutboundMessage
from app.channels.base.results import DeliveryReceipt
from app.core.config import settings

logger = logging.getLogger(__name__)

# Confirmed against Meta's Send API docs (Sprint 65 PR 5 research).
_NON_RETRYABLE_CODES = frozenset({190, 10, 100})
# Best-effort, not independently confirmed against a primary Meta source
# for Instagram specifically — Graph API's general rate-limit convention.
# See this module's docstring.
_RETRYABLE_CODES = frozenset({4, 32, 2})

# MediaKind -> Meta's `message.attachment.type` string (Sprint 65 PR 6,
# verified against current Meta docs — see module docstring).
_ATTACHMENT_TYPE = {
    MediaKind.IMAGE: "image",
    MediaKind.VIDEO: "video",
    MediaKind.AUDIO: "audio",
    MediaKind.DOCUMENT: "file",
}


def send_instagram_message(
    message: OutboundMessage,
    creds: ChannelCredentials,
    *,
    client: httpx.Client | None = None,
) -> DeliveryReceipt:
    """`client` is exposed only so tests can inject an `httpx.MockTransport`
    — same convention as `send_whatsapp_message`."""
    if creds.external_account_id is None:
        return DeliveryReceipt(
            status="failed",
            retryable=False,
            error="ChannelCredentials.external_account_id (Page id) is required "
            "to send an Instagram message",
        )

    if message.media:
        if len(message.media) > 1:
            logger.warning(
                "Instagram send received %d media items; sending only the first "
                "(Meta's attachment message accepts exactly one) — see send.py's "
                "module docstring",
                len(message.media),
            )
        media_ref = message.media[0]
        attachment_type = _ATTACHMENT_TYPE.get(media_ref.kind)
        if attachment_type is None:
            # Defensive only — every MediaKind value is mapped above, so this
            # should be unreachable via the real capability-gated send path.
            # Graceful failure, not an exception, per this PR's "never invent
            # behavior for an unsupported media type" requirement.
            return DeliveryReceipt(
                status="failed",
                retryable=False,
                error=f"Instagram does not support media kind '{media_ref.kind.value}'",
            )
        message_body = {"attachment": {"type": attachment_type, "payload": {"url": media_ref.url}}}
    else:
        message_body = {"text": message.text}

    url = (
        f"https://graph.facebook.com/{settings.instagram_graph_version}/"
        f"{creds.external_account_id}/messages"
    )
    headers = {"Authorization": f"Bearer {creds.access_token}"}
    payload = {
        "recipient": {"id": message.external_conversation_id},
        "message": message_body,
        "messaging_type": "RESPONSE",
    }

    owns_client = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        try:
            resp = client.post(url, headers=headers, json=payload)
        except httpx.RequestError as exc:
            logger.warning("Instagram send transport error: %s", type(exc).__name__)
            return DeliveryReceipt(
                status="failed", retryable=True, error=f"Network error: {type(exc).__name__}"
            )

        if resp.status_code >= 500:
            logger.warning("Instagram send failed with Meta %s", resp.status_code)
            return DeliveryReceipt(
                status="failed", retryable=True, error=f"Meta returned {resp.status_code}"
            )
        if resp.status_code >= 400:
            return _failed_receipt(resp)

        try:
            data = resp.json()
            message_id = data["message_id"]
        except (ValueError, KeyError, TypeError):
            # 2xx but a body that doesn't match Meta's documented shape —
            # Meta most likely already accepted it; retrying risks a
            # duplicate send, same reasoning as WhatsApp's identical case.
            logger.warning("Instagram send got a 2xx with an unrecognized response shape")
            return DeliveryReceipt(
                status="failed", retryable=False, error="Malformed success response from Meta"
            )
        return DeliveryReceipt(status="sent", external_message_id=message_id)
    finally:
        if owns_client:
            client.close()


def _failed_receipt(resp: httpx.Response) -> DeliveryReceipt:
    """Classifies a 4xx response. Only structured fields (status code,
    Meta's numeric error code/subcode) are logged or returned — never
    Meta's free-text error message or the raw response body, per this
    PR's error-handling requirement."""
    try:
        error = resp.json().get("error", {})
    except ValueError:
        error = {}
    code = error.get("code")
    subcode = error.get("error_subcode")

    retryable = code in _RETRYABLE_CODES
    logger.warning(
        "Instagram send rejected: status=%s code=%s subcode=%s retryable=%s",
        resp.status_code,
        code,
        subcode,
        retryable,
    )
    return DeliveryReceipt(
        status="failed",
        retryable=retryable,
        error=f"Meta rejected message: {resp.status_code} (code={code})",
    )
