"""WhatsApp (Meta Cloud API) webhook.

GET  /webhooks/whatsapp  — Meta subscription verification handshake.
POST /webhooks/whatsapp  — inbound messages. Verifies the request, resolves
the WhatsApp provider, parses the payload, and hands the result to
MessagingService. Returns 200 quickly so Meta does not retry.

Sprint 69 (self-serve WhatsApp): every business now brings its own Meta App,
so the HMAC signature is no longer verified against one shared global
secret — it must be verified against *that business's own* stored,
encrypted app secret. That requires knowing which business a payload is for
*before* the signature can be checked, which flips the natural order: the
payload's routing key is read first (untrusted), then the business (and its
stored credential) is looked up, and only then is the signature verified
with that business's own secret. Nothing from the payload is trusted or
persisted until that signature check passes.
The verify_token used by the GET handshake above stays a single shared
value on purpose — it's a one-time "prove you own this endpoint" handshake
Meta performs once per App, not a per-message trust boundary, so every
business is instructed to enter the same HIRA-provided value into their own
Meta App's webhook config (see documentation/WHATSAPP_INTEGRATION.md).

Sprint 64A PR 7 (webhook simplification): this route no longer parses Meta's
JSON itself, and no longer persists anything — both moved out, to
`WhatsAppProvider` (transport parsing) and `MessagingService` (persistence/
dedup/conversation lookup/enqueue) respectively. `receive()`'s job is now
exactly: verify the request, resolve the provider, parse the payload, hand
the result off. Business resolution for *authentication* purposes (which
business's secret to verify the signature against) stays here — that's
part of "verify the request," not message parsing or persistence.
"""

from __future__ import annotations

import hmac

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.processing import generate_and_store_reply
from app.channels.base.credentials import ChannelCredentials
from app.channels.base.errors import WebhookVerificationFailedError
from app.core.config import settings
from app.db.session import get_db
from app.models import Business
from app.services.channel_manager import ChannelManager
from app.services.messaging_service import MessagingService
from app.whatsapp.credentials import get_app_secret, get_stored_credential
from app.whatsapp.errors import WhatsAppCredentialError

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def get_reply_dispatcher():
    """Returns the callable that schedules reply generation. Overridable in tests."""

    def dispatch(
        background_tasks: BackgroundTasks, conversation_id, message_id, user_text: str
    ) -> None:
        background_tasks.add_task(generate_and_store_reply, conversation_id, message_id, user_text)

    return dispatch


@router.get("/whatsapp")
def verify_subscription(request: Request) -> Response:
    """Meta calls this once to verify the webhook. Echo the challenge if the
    verify token matches; otherwise 403."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    if mode == "subscribe" and hmac.compare_digest(token or "", settings.whatsapp_verify_token):
        return Response(content=challenge, media_type="text/plain")
    return Response(status_code=403)


async def _read_raw_body(request: Request) -> bytes:
    """The only part of this route that genuinely needs to be async (Starlette's
    Request.body() has no sync equivalent). FastAPI awaits dependencies
    regardless of whether the route itself is sync or async, so pulling this
    into its own dependency lets `receive` below be a plain `def` — see its
    docstring for why that matters (SCALE-1)."""
    return await request.body()


@router.post("/whatsapp")
def receive(
    request: Request,
    background_tasks: BackgroundTasks,
    raw_body: bytes = Depends(_read_raw_body),
    db: Session = Depends(get_db),
    dispatch=Depends(get_reply_dispatcher),
) -> Response:
    """SCALE-1: this used to be `async def`, but everything it does after
    reading the body — the signature check, and above all
    `MessagingService.record_inbound()`'s synchronous `db.scalars`/
    `db.commit()` calls — is blocking I/O. Under an `async def` route,
    FastAPI runs the whole function on the single event loop, so one slow
    Postgres round-trip stalls every other concurrent request the process
    is serving. A plain `def` route makes FastAPI run it in a worker
    thread instead, so this webhook (the highest-traffic endpoint in the
    app, and one Meta expects a fast ack from) can't starve the rest of
    the API under load.
    """
    provider = ChannelManager().resolve("whatsapp")

    try:
        phone_number_id = provider.extract_routing_key(raw_body)
    except WebhookVerificationFailedError:
        return Response(status_code=403)

    business = db.scalars(
        select(Business).where(Business.whatsapp_phone_number_id == phone_number_id)
    ).first()
    if business is None:
        return Response(status_code=403)

    credential = get_stored_credential(db, business.id)
    if credential is None:
        return Response(status_code=403)

    try:
        app_secret = get_app_secret(credential)
    except WhatsAppCredentialError:
        return Response(status_code=403)

    signing_creds = ChannelCredentials(channel="whatsapp", access_token="", secret=app_secret)
    if not provider.verify_webhook_signature(request.headers, raw_body, signing_creds):
        return Response(status_code=403)

    try:
        messages = provider.parse_webhook(raw_body)
    except WebhookVerificationFailedError:
        return Response(status_code=403)

    new_inbound = MessagingService(db).record_inbound(business.id, messages)

    if not settings.use_transactional_outbox:
        # Legacy path: schedule reply generation in-process, after the
        # webhook's DB transaction has already committed. When the outbox is
        # enabled the job was instead enqueued *inside* that transaction (see
        # MessagingService.record_inbound), so there is nothing to dispatch here.
        for conversation_id, message_id, _wa_message_id, user_text in new_inbound:
            dispatch(background_tasks, conversation_id, message_id, user_text)
    # Always 200 once persisted, so Meta does not retry.
    return Response(status_code=200, content='{"status":"received"}', media_type="application/json")
