"""Meta Conversions API for Business Messaging (Sprint 73).

Reports a conversion that happened inside a WhatsApp thread back to Meta, so
a business's Click-to-WhatsApp ads can optimize and measure against what
actually came of the conversation. Only one event is implemented:
`LeadSubmitted`, fired when a Lead moves into the `qualified` stage.

Two Graph API calls, nothing else:

* `GET  /{WABA_ID}/dataset`      -> the business's dataset id, cached on
                                    `Business.whatsapp_dataset_id`.
* `POST /{DATASET_ID}/events`    -> the event itself.

Both reuse the existing WhatsApp transport conventions verbatim —
`app.meta.graph_url()` for the URL and the business's own stored System User
token (`WhatsAppCredential`, via `app.whatsapp.credentials.get_access_token`)
for auth. No new credential, no new client, no new base URL.

The token needs the `whatsapp_business_manage_events` permission on top of
the `whatsapp_business_messaging`/`whatsapp_business_management` pair HIRA
already asks for; `whatsapp_business_management` is additionally required by
the dataset lookup. See documentation/WHATSAPP_INTEGRATION.md.

This module is pure transport: it takes ids and a click id, makes a call,
raises on failure. It has no database session, decides nothing about *when*
an event is worth sending, and never invents a dataset id or a ctwa_clid —
`app/whatsapp/conversion_tasks.py` owns that policy, and both values must
come from something Meta actually said.
"""

from __future__ import annotations

import logging

import httpx

from app import meta
from app.whatsapp.errors import WhatsAppCredentialError

logger = logging.getLogger(__name__)

# Sent as `partner_agent` on every event. Meta uses it to attribute traffic
# to the tech provider making the call; it is not a secret and not per-business.
PARTNER_AGENT = "hira"

LEAD_SUBMITTED = "LeadSubmitted"

_TIMEOUT = 10.0


class ConversionEventError(WhatsAppCredentialError):
    """A Conversions API call failed. `retryable` distinguishes a blip worth
    another attempt (5xx, network) from a permanent rejection (4xx) — the
    outbox handler maps it onto TransientJobError/PermanentJobError so the
    worker's existing retry policy applies unchanged."""

    def __init__(self, reason: str, *, retryable: bool) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retryable = retryable


def _check(resp: httpx.Response, what: str) -> None:
    """Raise unless Meta returned 2xx. 5xx is retryable, 4xx is not — a 4xx
    here means a bad dataset id, a token missing
    `whatsapp_business_manage_events`, or a malformed event, none of which a
    retry fixes. `resp.text` is Meta's own error body; it never contains the
    token (that travels in the Authorization header, not the URL)."""
    if resp.status_code >= 500:
        raise ConversionEventError(f"Meta returned {resp.status_code} for {what}", retryable=True)
    if resp.status_code >= 400:
        raise ConversionEventError(
            f"Meta rejected {what}: {resp.status_code} {resp.text}", retryable=False
        )


def resolve_dataset_id(
    whatsapp_business_account_id: str,
    access_token: str,
    *,
    client: httpx.Client | None = None,
) -> str:
    """The dataset id Conversions API events for this WABA are posted to.

    One live `GET /{WABA_ID}/dataset`. Meta returns `{"data": [{"id": ...}]}`;
    a WABA has exactly one dataset in practice, so the first entry is taken.
    Raises ConversionEventError if Meta returns no dataset at all rather than
    returning a placeholder — an unusable id would produce a silent
    never-delivered event, which is worse than a visible failure.
    """
    owns_client = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        try:
            resp = client.get(
                meta.graph_url(whatsapp_business_account_id, "dataset"),
                headers={"Authorization": f"Bearer {access_token}"},
            )
        except httpx.RequestError as exc:
            raise ConversionEventError(
                f"Could not reach Meta to look up the dataset id: {exc}", retryable=True
            ) from exc
        _check(resp, "the dataset lookup")
        data = resp.json().get("data") or []
        dataset_id = data[0].get("id") if data else None
        if not dataset_id:
            raise ConversionEventError(
                "Meta returned no dataset for this WhatsApp Business Account — "
                "the token may be missing the whatsapp_business_manage_events "
                "permission, or the WABA has no dataset yet.",
                retryable=False,
            )
        return str(dataset_id)
    finally:
        if owns_client:
            client.close()


def send_conversion_event(
    dataset_id: str,
    access_token: str,
    *,
    event_name: str,
    whatsapp_business_account_id: str,
    ctwa_clid: str,
    event_time: int,
    client: httpx.Client | None = None,
) -> None:
    """Post one Business Messaging conversion event.

    `ctwa_clid` is required, not optional: an event without the click that
    produced it has nothing for Meta to attribute against, so the caller must
    have one before reaching here (see conversion_tasks.py, which returns the
    "not attributable" state instead of calling this).
    """
    if not ctwa_clid:
        raise ConversionEventError(
            "Refusing to send a conversion event without a ctwa_clid", retryable=False
        )

    payload = {
        "data": [
            {
                "event_name": event_name,
                "event_time": event_time,
                "action_source": "business_messaging",
                "messaging_channel": "whatsapp",
                "user_data": {
                    "whatsapp_business_account_id": whatsapp_business_account_id,
                    "ctwa_clid": ctwa_clid,
                },
            }
        ],
        "partner_agent": PARTNER_AGENT,
    }

    owns_client = client is None
    client = client or httpx.Client(timeout=_TIMEOUT)
    try:
        try:
            resp = client.post(
                meta.graph_url(dataset_id, "events"),
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
            )
        except httpx.RequestError as exc:
            raise ConversionEventError(
                f"Could not reach Meta to send the conversion event: {exc}", retryable=True
            ) from exc
        _check(resp, f"the {event_name} conversion event")
        # Deliberately not parsed further: Meta's 200 body is a receipt
        # (events_received/messages), and nothing downstream acts on it. The
        # 200 itself is the success signal — no field of it is interpreted
        # as one.
        logger.info(
            "Sent %s conversion event to Meta (dataset=%s, waba=%s)",
            event_name,
            dataset_id,
            whatsapp_business_account_id,
        )
    finally:
        if owns_client:
            client.close()
