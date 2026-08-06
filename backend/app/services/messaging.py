"""Outbound WhatsApp messaging via the Meta Cloud API.

`send_text` posts a text message to the Graph API for a given business phone
number. It retries briefly on transient network/5xx errors. A client can be
injected for testing (httpx.MockTransport); otherwise a default client is used.

Note on the 24h window: free-form text like this is only deliverable inside the
customer-service window. Sending outside it requires a template message — out of
scope for the core loop (see documentation/WHATSAPP_INTEGRATION.md).
"""

from __future__ import annotations

import time

import httpx

from app.core.config import settings


class WhatsAppSendError(RuntimeError):
    """Non-retryable send failure (e.g. a 4xx client error)."""


class WhatsAppNotConnectedError(RuntimeError):
    """This business has no WhatsApp phone number configured yet."""


class _RetryableSendError(RuntimeError):
    """Transient failure (network or 5xx) worth retrying."""


def send_text(
    phone_number_id: str,
    to: str,
    body: str,
    *,
    access_token: str,
    client: httpx.Client | None = None,
    max_attempts: int = 3,
) -> str:
    """Send a text message; return the WhatsApp message id. Raises on failure.

    `access_token` is required and keyword-only (Sprint 69) — no default, so
    a caller can't accidentally fall through to a shared global token. Each
    business now has its own stored, encrypted access token
    (app/whatsapp/credentials.py); callers resolve it before calling this.

    Critical audit fix #2: every failure this function can encounter — an
    HTTP error status, a dropped connection, a timeout, or a 2xx response
    whose body doesn't parse the way Meta's API contract promises (not
    valid JSON, missing/renamed fields, an empty "messages" list, an
    unexpected shape) — surfaces as exactly one exception type,
    WhatsAppSendError. Callers (app/services/replies.py,
    app/ai/processing.py) can treat "any exception from this function" as
    "the send failed," full stop, without a partial except clause silently
    missing a failure mode this function could raise.
    """
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

    owns_client = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                resp = client.post(url, headers=headers, json=payload)

                if resp.status_code >= 500:
                    raise _RetryableSendError(f"Meta returned {resp.status_code}")
                if resp.status_code >= 400:
                    # 4xx is a client error — do not retry.
                    raise WhatsAppSendError(
                        f"Meta rejected message: {resp.status_code} {resp.text}"
                    )

                try:
                    data = resp.json()
                    return data["messages"][0]["id"]
                except (ValueError, KeyError, IndexError, TypeError) as exc:
                    # A 2xx status means Meta most likely already accepted
                    # (and sent) this message — retrying here, like the 4xx
                    # case above, would risk re-POSTing and duplicating a
                    # message the customer may have already received, so
                    # this fails immediately rather than going through the
                    # retry path below. ValueError covers json.JSONDecodeError
                    # (resp.json() raises a subclass of it) as well as a
                    # non-dict body; KeyError/IndexError/TypeError cover a
                    # 200 with an unexpected shape (a renamed/missing field,
                    # an empty "messages" list, "messages" not being a list
                    # at all, ...).
                    raise WhatsAppSendError(
                        f"Meta returned {resp.status_code} but the response body was not "
                        f"a well-formed send confirmation: {exc!r}"
                    ) from exc
            except (httpx.RequestError, _RetryableSendError) as exc:
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
