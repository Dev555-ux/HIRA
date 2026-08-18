"""Outbound send — transport boundary stub. Implementation target for
Sprint 65 PR 5.

Purpose: define the DTO-shaped call `InstagramProvider.send()` makes and
what it must return, so the later PR that fills this in is implementing
against an already-agreed contract, not inventing one mid-PR.

Does NOT implement the Graph API call — Sprint 65 PR 1 makes no Meta
calls (foundation only). What's documented below is the expected shape,
based on Meta's documented Instagram Messaging "Send API" at the time of
writing; re-verify against Meta's current docs before implementing it —
none of this has been tested against a live account.

Expected request (a later PR builds this):

    POST https://graph.facebook.com/{graph_version}/{ig_business_account_id}/messages
    Authorization: Bearer {access_token}
    {
        "recipient": {"id": "<IGSID>"},
        "message": {"text": "<body>"}
    }

Expected response on success:

    {"recipient_id": "<IGSID>", "message_id": "<mid>"}

Expected failure shape: Meta's standard Graph API error envelope
(`{"error": {"message": ..., "type": ..., "code": ..., ...}}`), same
family of HTTP status codes as WhatsApp's Cloud API (4xx client error —
not retryable; 5xx — retryable) since both are Graph API products, though
Instagram's specific error codes for messaging-window violations, rate
limits, etc. are not yet catalogued here — that classification work
(mirroring `app.channels.whatsapp.send`'s `retryable` mapping — see
documentation/architecture/messaging-platform.md §5) is part of
implementing this function for real, not something to guess at now.

Instagram, like WhatsApp, enforces a messaging window (Meta's "24-hour
standard messaging window," plus a small set of tag-based exceptions for
specific post-window message types) — sending outside it will fail with a
specific Graph API error this function will eventually need to recognize.
Not modeled here; flagged so PR 5 doesn't rediscover it from scratch.
"""

from __future__ import annotations

from app.channels.base.credentials import ChannelCredentials
from app.channels.base.message import OutboundMessage
from app.channels.base.results import DeliveryReceipt


def send_instagram_message(message: OutboundMessage, creds: ChannelCredentials) -> DeliveryReceipt:
    """Implementation target for Sprint 65 PR 5. Deliberately raises
    rather than returning a fake `DeliveryReceipt` — a placeholder
    "success" or "failure" here would be indistinguishable from a real,
    tested transport call, which is exactly the invented behavior this
    PR is instructed not to produce."""
    raise NotImplementedError(
        "Instagram outbound send is not implemented — Sprint 65 PR 1 is foundation "
        "only (no Meta API calls). See this module's docstring for the expected "
        "Graph API request/response shape this function must eventually build, "
        "and app.channels.whatsapp.send for the pattern (single attempt, "
        "DeliveryReceipt.retryable classification, no internal retry loop) to follow."
    )
