"""Outbound send — a thin DTO-shaped wrapper around the existing
`app.services.messaging.send_text`.

Purpose: let `WhatsAppProvider.send()` accept/return the PR 2 DTOs without
touching the Graph API call itself.

Does NOT do: retry, build the Graph API request, or change authentication —
all of that is exactly what `send_text` already does; this module reuses it
verbatim. PR 3's explicit instruction is "reuse send_text(), do not change
retry behavior," so the 3-attempt retry that already lives inside
`send_text` (app/services/messaging.py:70-131) stays there for now,
unchanged. Note this temporarily diverges from `ChannelProvider.send()`'s
own docstring contract ("a single attempt — no retry loop... ChannelManager
owns retry policy"), which describes the target end state once a later PR
moves that retry logic up into ChannelManager and this wrapper calls a
single-attempt Graph API function instead. Until then, `send_text`'s retry
runs exactly as it does in production today.

Future integration point: called by `WhatsAppProvider.send()`. Once
ChannelManager gains real retry policy, this function's body is what gets
replaced with a single-attempt call — the DTO-shaped signature it exposes
today doesn't need to change.
"""

from __future__ import annotations

import httpx

from app.channels.base.credentials import ChannelCredentials
from app.channels.base.message import OutboundMessage
from app.channels.base.results import DeliveryReceipt
from app.services.messaging import WhatsAppSendError, send_text


def send_whatsapp_message(
    message: OutboundMessage,
    creds: ChannelCredentials,
    *,
    client: httpx.Client | None = None,
) -> DeliveryReceipt:
    """`client` is exposed only so tests can inject an `httpx.MockTransport`,
    same as `send_text` itself already allows."""
    if creds.external_account_id is None:
        return DeliveryReceipt(
            status="failed",
            error="ChannelCredentials.external_account_id (phone_number_id) is required "
            "to send a WhatsApp message",
        )
    try:
        wa_message_id = send_text(
            creds.external_account_id,
            message.external_conversation_id,
            message.text,
            access_token=creds.access_token,
            client=client,
        )
    except WhatsAppSendError as exc:
        return DeliveryReceipt(status="failed", error=str(exc))
    return DeliveryReceipt(status="sent", external_message_id=wa_message_id)
