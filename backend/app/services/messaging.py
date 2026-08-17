"""Outbound WhatsApp messaging via the Meta Cloud API.

`send_text` posts a text message to the Graph API for a given business phone
number. It retries briefly on transient network/5xx errors. A client can be
injected for testing (httpx.MockTransport); otherwise a default client is used.

Note on the 24h window: free-form text like this is only deliverable inside the
customer-service window. Sending outside it requires a template message — out of
scope for the core loop (see documentation/WHATSAPP_INTEGRATION.md).

Sprint 64A PR 6 (outbound cutover): `send_text`'s single-HTTP-call-and-
classify step is now `send_text_once()` below, extracted so
`app.channels.whatsapp.send` (WhatsAppProvider's one transport attempt) and
`send_text`'s own retry loop share one implementation instead of two. Kept
here rather than moved into `app/channels/whatsapp/`, since it's still
`send_text`'s own building block too — `send_text` itself is unchanged in
behavior, still directly used by tests/test_messaging.py and still the
thing `send_via_channel_manager()` (also below) exists to eventually
retire, once every caller through PR 6 has proven equivalent.
"""

from __future__ import annotations

import time

import httpx

from app.channels.base.credentials import ChannelCredentials
from app.channels.base.errors import ChannelError
from app.channels.base.message import OutboundMessage
from app.core.config import settings
from app.services.channel_manager import ChannelManager


class WhatsAppSendError(RuntimeError):
    """Non-retryable send failure (e.g. a 4xx client error)."""


class WhatsAppNotConnectedError(RuntimeError):
    """This business has no WhatsApp phone number configured yet."""


class RetryableSendError(RuntimeError):
    """Transient failure (network or 5xx) worth retrying.

    Public (no longer `_RetryableSendError`) as of Sprint 64A PR 6:
    `app.channels.whatsapp.send` needs to catch this too, to classify a
    single Graph API attempt exactly the way `send_text`'s retry loop
    always has — same convention as `signature_valid`'s PR 4 relocation
    (app/channels/whatsapp/parsing.py), a name only needs to be private
    until a second module genuinely needs it.
    """


def _build_send_request(
    phone_number_id: str, to: str, body: str, access_token: str
) -> tuple[str, dict[str, str], dict[str, object]]:
    url = (
        f"{settings.whatsapp_api_base}/{settings.whatsapp_graph_version}/{phone_number_id}/messages"
    )
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }
    return url, headers, payload


def send_text_once(
    phone_number_id: str,
    to: str,
    body: str,
    *,
    access_token: str,
    client: httpx.Client | None = None,
) -> str:
    """A single Graph API attempt — no retry loop, no backoff. Returns the
    WhatsApp message id on success.

    Raises `RetryableSendError` for a 5xx status — the caller (`send_text`'s
    own loop, or ChannelManager) decides whether trying again is worth it.
    A network/transport failure (`httpx.RequestError` and subclasses) is
    not caught here; it propagates as-is, exactly as it always has out of
    `send_text`'s inner `client.post()` call — every caller of this
    function already needs to handle both `RetryableSendError` and
    `httpx.RequestError` as "retryable" for identical treatment.

    Raises `WhatsAppSendError` — never retried, by either caller — for a
    4xx status, or a 2xx response whose body doesn't parse the way Meta's
    API contract promises (not valid JSON, missing/renamed fields, an
    empty "messages" list, an unexpected shape): a 2xx status means Meta
    most likely already accepted (and sent) this message, so retrying
    would risk re-POSTing and duplicating a message the customer may have
    already received.
    """
    url, headers, payload = _build_send_request(phone_number_id, to, body, access_token)
    owns_client = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        resp = client.post(url, headers=headers, json=payload)

        if resp.status_code >= 500:
            raise RetryableSendError(f"Meta returned {resp.status_code}")
        if resp.status_code >= 400:
            raise WhatsAppSendError(f"Meta rejected message: {resp.status_code} {resp.text}")

        try:
            data = resp.json()
            return data["messages"][0]["id"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            # ValueError covers json.JSONDecodeError (resp.json() raises a
            # subclass of it) as well as a non-dict body; KeyError/
            # IndexError/TypeError cover a 200 with an unexpected shape (a
            # renamed/missing field, an empty "messages" list, "messages"
            # not being a list at all, ...).
            raise WhatsAppSendError(
                f"Meta returned {resp.status_code} but the response body was not "
                f"a well-formed send confirmation: {exc!r}"
            ) from exc
    finally:
        if owns_client:
            client.close()


def send_text(
    phone_number_id: str,
    to: str,
    body: str,
    *,
    access_token: str,
    client: httpx.Client | None = None,
    max_attempts: int = 3,
) -> str:
    """Send a text message with up to `max_attempts` tries; return the
    WhatsApp message id. Raises on failure.

    `access_token` is required and keyword-only (Sprint 69) — no default, so
    a caller can't accidentally fall through to a shared global token. Each
    business now has its own stored, encrypted access token
    (app/whatsapp/credentials.py); callers resolve it before calling this.

    Critical audit fix #2: every failure this function can encounter —
    surfaces as exactly one exception type, WhatsAppSendError. Callers can
    treat "any exception from this function" as "the send failed," full
    stop, without a partial except clause silently missing a failure mode
    this function could raise.

    Retry loop unchanged since before Sprint 64A PR 6 — same conditions
    (5xx or a network/transport error is retried, a 4xx or malformed body
    is not), same backoff (`0.2 * attempt` between tries), same client
    lifecycle (one client, created here if not injected, reused across all
    attempts, closed once at the end). Only the single-HTTP-call-and-
    classify step now delegates to `send_text_once()` instead of
    duplicating it inline.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                return send_text_once(
                    phone_number_id, to, body, access_token=access_token, client=client
                )
            except (httpx.RequestError, RetryableSendError) as exc:
                # httpx.RequestError (not just its TransportError subclass):
                # every network/transport-shaped failure httpx itself can
                # raise from client.post() — timeouts, connection errors,
                # protocol errors — plus DecodingError (a corrupt
                # transport-level response body, distinct from the JSON
                # parsing failure above) and TooManyRedirects. All of these
                # mean the request itself never definitively completed, so
                # retrying is safe the same way a 5xx is.
                last_error = exc
                if attempt < max_attempts:
                    time.sleep(0.2 * attempt)
        raise WhatsAppSendError(f"Failed to send after {max_attempts} attempts: {last_error}")
    except WhatsAppSendError:
        raise
    except Exception as exc:
        # Safety net: no failure mode reaching this function should ever
        # surface to a caller as anything other than WhatsAppSendError —
        # see this function's own docstring. Anything not already
        # anticipated above (an httpx internal this module didn't name, a
        # bug in this function itself) still becomes one, rather than
        # leaking a raw exception a caller has no reason to know how to
        # handle (Critical audit fix #2, Part A).
        raise WhatsAppSendError(f"Unexpected error sending WhatsApp message: {exc!r}") from exc
    finally:
        if owns_client:
            client.close()


def send_via_channel_manager(
    phone_number_id: str,
    to: str,
    body: str,
    *,
    access_token: str,
) -> str:
    """Sprint 64A PR 6 — the new default `sender` for
    `app.ai.processing`/`app.services.replies`/`app.api.dashboard`,
    replacing `send_text` as the production outbound entry point.

    Preserves `send_text`'s exact call signature and exception contract
    (raise `WhatsAppSendError` on any failure, return the provider message
    id on success) so every existing caller — and their existing except
    clauses, e.g. `app/api/dashboard.py::approve_message`'s
    `WhatsAppSendError` -> 502 mapping — needs zero changes. Internally
    routes through `ChannelManager` -> the channel registry ->
    `WhatsAppProvider.send()` instead of calling the Graph API directly;
    retry now lives in `ChannelManager`, not here.

    This is a thin adapter, not a rewrite of the calling contract: the
    `Callable[..., str] = send_text`-shaped injection point in
    `_auto_send`/`generate_reply_into_session`/`approve_and_send` is
    unchanged, only its default value is. A future PR (Sprint 64A PR 7+)
    that extracts MessagingService can replace these call sites with a
    direct `MessagingService.send_reply()` call and retire this adapter
    (and `send_text` itself, once nothing production still points at it —
    see that function's own module-level note).
    """
    message = OutboundMessage(channel="whatsapp", external_conversation_id=to, text=body)
    creds = ChannelCredentials(
        channel="whatsapp", access_token=access_token, external_account_id=phone_number_id
    )
    try:
        receipt = ChannelManager().send(message, creds)
    except ChannelError as exc:
        # Provider lookup / capability failure — a configuration problem,
        # not an ordinary delivery failure, but callers of this adapter
        # only know how to handle WhatsAppSendError (see docstring above).
        raise WhatsAppSendError(str(exc)) from exc
    if receipt.status == "failed":
        raise WhatsAppSendError(receipt.error or "WhatsApp send failed")
    assert receipt.external_message_id is not None  # invariant when status == "sent"
    return receipt.external_message_id
