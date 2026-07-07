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
import traceback

import httpx

from app.core.config import settings


class WhatsAppSendError(RuntimeError):
    """Non-retryable send failure (e.g. a 4xx client error)."""


class _RetryableSendError(RuntimeError):
    """Transient failure (network or 5xx) worth retrying."""


def send_text(
    phone_number_id: str,
    to: str,
    body: str,
    *,
    client: httpx.Client | None = None,
    max_attempts: int = 3,
) -> str:
    """Send a text message; return the WhatsApp message id. Raises on failure."""
    url = (
        f"{settings.whatsapp_api_base}/{settings.whatsapp_graph_version}/{phone_number_id}/messages"
    )
    headers = {"Authorization": f"Bearer {settings.whatsapp_access_token}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": body},
    }

    # TEMPORARY DIAGNOSTIC — remove after debugging outbound send.
    token = settings.whatsapp_access_token or ""
    masked_token = token[:8] + "*" * max(len(token) - 8, 0) if token else "<empty>"
    print(
        "\n======== GRAPH REQUEST ========\n"
        f"URL: {url}\n"
        f"Headers: {{'Authorization': 'Bearer {masked_token}'}}\n"
        f"Payload: {payload}\n"
        "===============================",
        flush=True,
    )

    owns_client = client is None
    client = client or httpx.Client(timeout=10.0)
    try:
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                try:
                    resp = client.post(url, headers=headers, json=payload)

                    # TEMPORARY DIAGNOSTIC
                    print(
                        "\n======== GRAPH RESPONSE ========\n"
                        f"Status code: {resp.status_code}\n"
                        f"Response body: {resp.text}\n"
                        "================================",
                        flush=True,
                    )

                    if resp.status_code >= 500:
                        raise _RetryableSendError(f"Meta returned {resp.status_code}")
                    if resp.status_code >= 400:
                        # 4xx is a client error — do not retry.
                        raise WhatsAppSendError(
                            f"Meta rejected message: {resp.status_code} {resp.text}"
                        )
                    data = resp.json()
                    wa_message_id = data["messages"][0]["id"]

                    # TEMPORARY DIAGNOSTIC
                    print(f"[DIAG] Returned wamid: {wa_message_id}", flush=True)

                    return wa_message_id
                except Exception:
                    # TEMPORARY DIAGNOSTIC — surface the full traceback for ANY
                    # exception on this attempt (network error, bad JSON, missing
                    # key, etc.), then re-raise unchanged so the retry/error
                    # handling below behaves exactly as before.
                    print("\n======== send_text EXCEPTION (attempt %d) ========" % attempt, flush=True)
                    print(traceback.format_exc(), flush=True)
                    print("===================================================\n", flush=True)
                    raise
            except (httpx.TransportError, _RetryableSendError) as exc:
                last_error = exc
                if attempt < max_attempts:
                    time.sleep(0.2 * attempt)
        raise WhatsAppSendError(f"Failed to send after {max_attempts} attempts: {last_error}")
    finally:
        if owns_client:
            client.close()
