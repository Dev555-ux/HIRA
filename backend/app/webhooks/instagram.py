"""Instagram (Meta Messenger Platform) webhook.

GET  /webhooks/instagram  — Meta subscription verification handshake.
POST /webhooks/instagram  — inbound Direct Messages. Verifies the request,
resolves the Instagram provider, parses the payload, and hands the result
to MessagingService. Returns 200 quickly so Meta does not retry.

Mirrors app/webhooks/whatsapp.py's post-Sprint-64A-PR-7 shape exactly:
verify, resolve provider, parse, hand off — no persistence, no conversation
logic, no customer lookup, no dedup, no AI logic in this file.

One real difference from WhatsApp's route, not a design choice made here:
Instagram's OAuth (Sprint 65 PR 2) connects every business through one
HIRA-owned Meta App (`settings.instagram_app_id`/`instagram_app_secret`),
not a bring-your-own-app model like WhatsApp's self-serve flow. So every
Instagram webhook delivery to HIRA's one callback URL is signed with the
same shared app secret, regardless of which business it's for — signature
verification does not need to know the business first, unlike WhatsApp's
per-business app secret, which forces routing-key-then-verify ordering
there. Verifying first here is simpler and strictly safer: nothing is
parsed or looked up from a payload before its signature is trusted.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy.orm import Session

from app.channels.base.credentials import ChannelCredentials
from app.channels.base.errors import WebhookVerificationFailedError
from app.core.config import settings
from app.db.session import get_db
from app.instagram.credentials import get_credential_by_ig_account_id
from app.services.channel_manager import ChannelManager
from app.services.messaging_service import MessagingService
from app.webhooks.whatsapp import get_reply_dispatcher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/instagram")
def verify_subscription(request: Request) -> Response:
    """Meta calls this once to verify the webhook. Delegates to
    InstagramProvider.verify_subscription() (already implemented and
    tested in Sprint 65 PR 1) rather than re-checking
    settings.instagram_verify_token inline here — see that method's
    docstring for why the token is a distinct setting, not a reuse of
    WhatsApp's."""
    provider = ChannelManager().resolve("instagram")
    creds = ChannelCredentials(channel="instagram", access_token="")
    challenge = provider.verify_subscription(request.query_params, creds)
    if challenge is None:
        # No customer content, no secret in this query string worth
        # withholding (hub.verify_token is compared, never echoed) — safe
        # to log the mode/presence of a token, useful for diagnosing a
        # misconfigured Meta App webhook setup.
        logger.warning(
            "Instagram webhook verification failed: hub.mode=%s token_present=%s",
            request.query_params.get("hub.mode"),
            "hub.verify_token" in request.query_params,
        )
        return Response(status_code=403)
    logger.info("Instagram webhook verification succeeded")
    return Response(content=challenge, media_type="text/plain")


async def _read_raw_body(request: Request) -> bytes:
    """See app/webhooks/whatsapp.py's identical helper's docstring (SCALE-1)
    for why this is the only async part of the route."""
    return await request.body()


@router.post("/instagram")
def receive(
    request: Request,
    background_tasks: BackgroundTasks,
    raw_body: bytes = Depends(_read_raw_body),
    db: Session = Depends(get_db),
    dispatch=Depends(get_reply_dispatcher),
) -> Response:
    """Plain `def`, not `async def` — same SCALE-1 reasoning as
    app/webhooks/whatsapp.py::receive(): MessagingService.record_inbound()
    does blocking Postgres I/O, so this needs to run in a worker thread,
    not FastAPI's single event loop."""
    provider = ChannelManager().resolve("instagram")

    signing_creds = ChannelCredentials(
        channel="instagram", access_token="", secret=settings.instagram_app_secret or None
    )
    if not provider.verify_webhook_signature(request.headers, raw_body, signing_creds):
        # Deliberately doesn't distinguish "signature didn't match" from
        # "INSTAGRAM_APP_SECRET isn't configured" in the response (both are
        # 403 to the caller — Meta shouldn't learn which), but does in the
        # log line, since an ops person debugging "why is Instagram down"
        # needs to tell a real forged request apart from a missing env var.
        # Never logs the signature header or raw_body itself.
        logger.warning(
            "Instagram webhook signature verification failed (app_secret_configured=%s)",
            bool(settings.instagram_app_secret),
        )
        return Response(status_code=403)

    try:
        account_id = provider.extract_routing_key(raw_body)
    except WebhookVerificationFailedError:
        logger.warning("Instagram webhook body malformed or missing a routing id")
        return Response(status_code=403)

    credential = get_credential_by_ig_account_id(db, account_id)
    if credential is None:
        # No business has connected this Instagram account — nothing to
        # route to. Not an error condition worth a 5xx; Meta should not
        # retry a delivery no business is waiting for. account_id is
        # Meta's own IG Business Account id, not customer content — safe
        # to log for diagnosing "which account tried to deliver here."
        logger.warning("Instagram webhook for unconnected IG account %s", account_id)
        return Response(status_code=403)

    try:
        messages = provider.parse_webhook(raw_body)
    except WebhookVerificationFailedError:
        logger.warning(
            "Instagram webhook payload failed to parse for business %s", credential.business_id
        )
        return Response(status_code=403)

    new_inbound = MessagingService(db).record_inbound(credential.business_id, messages)
    logger.info(
        "Instagram webhook delivered %d message(s), %d new, for business %s",
        len(messages),
        len(new_inbound),
        credential.business_id,
    )

    if not settings.use_transactional_outbox:
        # Legacy path — see app/webhooks/whatsapp.py::receive()'s identical
        # block for why this only runs when the outbox is disabled.
        for conversation_id, message_id, _external_message_id, user_text in new_inbound:
            dispatch(background_tasks, conversation_id, message_id, user_text)
    # Always 200 once persisted, so Meta does not retry.
    return Response(status_code=200, content='{"status":"received"}', media_type="application/json")
