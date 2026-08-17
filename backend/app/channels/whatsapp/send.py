"""Outbound send — a thin DTO-shaped wrapper around
`app.services.messaging.send_text_once`.

Purpose: let `WhatsAppProvider.send()` accept/return the PR 2 DTOs without
touching the Graph API call itself.

Does NOT do: retry (Sprint 64A PR 6 — this is now exactly one transport
attempt, per `ChannelProvider.send()`'s own contract), build the Graph API
request, or change authentication — all of that is exactly what
`send_text_once` already does; this module reuses it verbatim rather than
duplicating it. Retry now lives in `app.services.channel_manager.
ChannelManager.send()`, which calls `WhatsAppProvider.send()` (this
module, transitively) up to its own `max_attempts` times, using
`DeliveryReceipt.retryable` (set below) to decide whether another attempt
is worth it — without ChannelManager ever needing to know a Graph API
status code exists.

Future integration point: called by `WhatsAppProvider.send()`.
"""

from __future__ import annotations

import httpx

from app.channels.base.credentials import ChannelCredentials
from app.channels.base.message import OutboundMessage
from app.channels.base.results import DeliveryReceipt
from app.services.messaging import RetryableSendError, WhatsAppSendError, send_text_once


def send_whatsapp_message(
    message: OutboundMessage,
    creds: ChannelCredentials,
    *,
    client: httpx.Client | None = None,
) -> DeliveryReceipt:
    """`client` is exposed only so tests can inject an `httpx.MockTransport`,
    same as `send_text_once` itself already allows.

    `retryable=True` mirrors exactly what `send_text`'s own retry loop has
    always treated as worth retrying: a 5xx status (`RetryableSendError`)
    or a network/transport failure (`httpx.RequestError`, not caught by
    `send_text_once` itself — it propagates straight out of `client.post()`,
    same as it always has). `retryable=False` mirrors what was never
    retried: a 4xx status or a malformed 2xx body (both raise
    `WhatsAppSendError`), or any other unexpected exception — the same
    "unexpected -> stop, don't retry blindly" treatment `send_text`'s own
    safety net gives.
    """
    if creds.external_account_id is None:
        return DeliveryReceipt(
            status="failed",
            retryable=False,
            error="ChannelCredentials.external_account_id (phone_number_id) is required "
            "to send a WhatsApp message",
        )
    try:
        wa_message_id = send_text_once(
            creds.external_account_id,
            message.external_conversation_id,
            message.text,
            access_token=creds.access_token,
            client=client,
        )
    except RetryableSendError as exc:
        return DeliveryReceipt(status="failed", retryable=True, error=str(exc))
    except httpx.RequestError as exc:
        return DeliveryReceipt(status="failed", retryable=True, error=str(exc))
    except WhatsAppSendError as exc:
        return DeliveryReceipt(status="failed", retryable=False, error=str(exc))
    except Exception as exc:  # noqa: BLE001 — safety net, mirrors send_text's own
        return DeliveryReceipt(
            status="failed",
            retryable=False,
            error=f"Unexpected error sending WhatsApp message: {exc!r}",
        )
    return DeliveryReceipt(status="sent", external_message_id=wa_message_id)
