"""WhatsApp (Meta Cloud API) webhook.

GET  /webhooks/whatsapp  — Meta subscription verification handshake.
POST /webhooks/whatsapp  — inbound messages. Verifies the HMAC signature,
dedupes by message id, persists the inbound message, and returns 200 quickly.

Heavy work (AI orchestration) is intentionally NOT done here yet — that is
dispatched later (S1-08+). The webhook's job is to authenticate, record, and
acknowledge fast so Meta does not retry.

Sprint 69 (self-serve WhatsApp): every business now brings its own Meta App,
so the HMAC signature is no longer verified against one shared global
secret — it must be verified against *that business's own* stored,
encrypted app secret. That requires knowing which business a payload is for
*before* the signature can be checked, which flips the original order: the
payload is now parsed (as untrusted JSON) first, purely to read
`phone_number_id` out of it, then the business (and its stored credential)
is looked up, and only then is the signature verified with that business's
own secret. Nothing from the payload is trusted or persisted until that
signature check passes — parsing untrusted JSON to read one field is safe;
acting on its contents before authentication is not, and this code doesn't.
The verify_token used by the GET handshake above stays a single shared
value on purpose — it's a one-time "prove you own this endpoint" handshake
Meta performs once per App, not a per-message trust boundary, so every
business is instructed to enter the same HIRA-provided value into their own
Meta App's webhook config (see documentation/WHATSAPP_INTEGRATION.md).

Sprint 64A PR 5 (inbound cutover): `_persist_inbound` no longer parses Meta
message objects inline — it calls `app.channels.whatsapp.parsing.
parse_messages()`, the same function `WhatsAppProvider.parse_webhook()` and
Shadow Mode (PR 4) already used, so there is exactly one implementation of
"Meta message dict -> normalized fields" in the codebase. Business
resolution, customer/conversation lookup, deduplication, persistence, and
job enqueueing are all unchanged — only where the message content itself
gets extracted moved. Shadow Mode's runtime scheduling is removed from
`receive()` as of this PR (nothing left to shadow-compare against, now
that production and Shadow Mode share one parser) — `app/channels/
whatsapp/shadow.py` itself, its tests, and its config flag are untouched
and available for a future migration to repoint.
"""

from __future__ import annotations

import hmac
import json
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai.processing import generate_and_store_reply
from app.ai.tasks import GENERATE_AI_REPLY_TASK
from app.channels.whatsapp.parsing import parse_messages, signature_valid
from app.core.config import settings
from app.db.session import get_db
from app.jobs import enqueue_job
from app.models import Business, Conversation, Customer, Message
from app.whatsapp.credentials import get_app_secret, get_stored_credential
from app.whatsapp.errors import WhatsAppCredentialError

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

SERVICE_WINDOW = timedelta(hours=24)


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


def _first_phone_number_id(payload: dict) -> str | None:
    """A single webhook delivery is signed once, by one Meta App — so every
    entry/change within it belongs to the same business. Reading the first
    one found is enough to know which business's secret to verify against."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            phone_number_id = change.get("value", {}).get("metadata", {}).get("phone_number_id")
            if phone_number_id:
                return phone_number_id
    return None


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
    reading the body — the signature check, and above all `_persist_inbound`'s
    synchronous `db.scalars`/`db.commit()` calls — is blocking I/O. Under an
    `async def` route, FastAPI runs the whole function on the single event
    loop, so one slow Postgres round-trip stalls every other concurrent
    request the process is serving. A plain `def` route makes FastAPI run it
    in a worker thread instead, so this webhook (the highest-traffic endpoint
    in the app, and one Meta expects a fast ack from) can't starve the rest
    of the API under load.
    """
    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return Response(status_code=403)

    phone_number_id = _first_phone_number_id(payload)
    if phone_number_id is None:
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

    if not signature_valid(raw_body, request.headers.get("X-Hub-Signature-256"), app_secret):
        return Response(status_code=403)

    new_inbound = _persist_inbound(db, payload)

    if not settings.use_transactional_outbox:
        # Legacy path: schedule reply generation in-process, after the
        # webhook's DB transaction has already committed. When the outbox is
        # enabled the job was instead enqueued *inside* that transaction (see
        # _persist_inbound), so there is nothing to dispatch here.
        for conversation_id, message_id, _wa_message_id, user_text in new_inbound:
            dispatch(background_tasks, conversation_id, message_id, user_text)
    # Always 200 once persisted, so Meta does not retry.
    return Response(status_code=200, content='{"status":"received"}', media_type="application/json")


def _persist_inbound(db: Session, payload: dict) -> list[tuple]:
    """Persist inbound messages; return (conversation_id, message_id,
    wa_message_id, text) for new ones.

    When `use_transactional_outbox` is enabled, the AI-reply job is enqueued
    here — *inside* the same transaction that persists the inbound Message and
    before its commit — so the message and its job land atomically (the whole
    point of a transactional outbox: no inbound message can be recorded without
    its reply-generation job, and vice versa). When disabled, nothing is
    enqueued and reply generation is scheduled by the caller after commit, via
    the legacy BackgroundTasks path.

    Business resolution stays per-`change` and inline here (routing/
    persistence concern, not message parsing — `NormalizedMessage` has no
    `phone_number_id`/business field, only the *customer's* phone number).
    Only the "Meta message dict -> normalized fields" step delegates to
    `parse_messages()` (Sprint 64A PR 5) — see that function's docstring.
    """
    new_inbound: list[tuple] = []
    now = datetime.now(timezone.utc)
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            # Ignore delivery/status callbacks: they carry "statuses", not "messages".
            if not value.get("messages"):
                continue
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            business = db.scalars(
                select(Business).where(Business.whatsapp_phone_number_id == phone_number_id)
            ).first()
            if business is None:
                continue  # unknown number — ignore gracefully

            normalized_messages = parse_messages(
                value.get("messages", []), value.get("contacts", [])
            )
            for normalized in normalized_messages:
                # Read straight from the original Meta message object
                # (carried unchanged on `.raw`) for these two fields rather
                # than NormalizedMessage's own `external_message_id`/
                # `external_sender_id` — those default missing values to
                # `""`, while this dedupe/lookup logic (unchanged from
                # before PR 5) relies on `msg.get(...)` defaulting to
                # `None`. Meta always sends both on a real message, so this
                # never differs in practice; reading from `.raw` keeps it
                # byte-for-byte identical to pre-PR-5 behavior even in the
                # unreachable case where it's missing.
                wa_message_id = normalized.raw.get("id")
                already = db.scalars(
                    select(Message).where(Message.wa_message_id == wa_message_id)
                ).first()
                if already is not None:
                    continue  # dedupe

                wa_phone = normalized.raw.get("from")
                customer = _get_or_create_customer(
                    db, business.id, wa_phone, normalized.sender_display_name
                )
                conversation = _get_or_create_conversation(db, business.id, customer.id, now)

                body = normalized.text
                message = Message(
                    conversation_id=conversation.id,
                    business_id=business.id,
                    direction="inbound",
                    wa_message_id=wa_message_id,
                    body=body,
                    type=normalized.raw.get("type", "text"),
                    status="received",
                )
                db.add(message)
                db.flush()
                conversation.last_message_at = now
                conversation.window_expires_at = now + SERVICE_WINDOW

                if settings.use_transactional_outbox:
                    # Idempotency key namespaced on the stable WhatsApp message
                    # id (UNIQUE across redeliveries), so a duplicate webhook
                    # delivery can never enqueue a second reply job even if it
                    # somehow got past the wa_message_id dedupe above. enqueue_job
                    # only flushes inside this transaction — it does not commit —
                    # so the job rides the same commit as the Message below.
                    enqueue_job(
                        db,
                        business_id=business.id,
                        task_name=GENERATE_AI_REPLY_TASK,
                        payload={
                            "conversation_id": str(conversation.id),
                            "message_id": str(message.id),
                            "user_text": body,
                        },
                        idempotency_key=f"whatsapp:{wa_message_id}",
                    )

                new_inbound.append((conversation.id, message.id, wa_message_id, body))
            db.commit()
    return new_inbound


def _get_or_create_customer(
    db: Session, business_id, wa_phone: str, display_name: str | None
) -> Customer:
    """Get-or-create, race-safe against `uq_customer_business_phone`.

    Two overlapping webhook deliveries for the same phone number (e.g. a
    Meta retry landing concurrently with the original) can both pass the
    SELECT below before either flushes. On conflict, a plain `db.rollback()`
    would also discard any *other* messages already staged earlier in this
    same `_persist_inbound` batch (one commit covers a whole `change`'s
    messages) — so the insert attempt runs in a SAVEPOINT via
    `begin_nested()`, whose rollback-on-conflict only undoes this one row.
    """
    customer = db.scalars(
        select(Customer).where(Customer.business_id == business_id, Customer.wa_phone == wa_phone)
    ).first()
    if customer is not None:
        return customer
    try:
        with db.begin_nested():
            customer = Customer(
                business_id=business_id, wa_phone=wa_phone, display_name=display_name
            )
            db.add(customer)
            db.flush()
    except IntegrityError:
        customer = db.scalars(
            select(Customer).where(
                Customer.business_id == business_id, Customer.wa_phone == wa_phone
            )
        ).first()
        if customer is None:
            raise
    return customer


def _get_or_create_conversation(db: Session, business_id, customer_id, now) -> Conversation:
    """Get-or-create. Unlike `_get_or_create_customer`, there is no unique
    constraint on (business_id, customer_id, status) for Conversation, so a
    concurrent race here can't raise IntegrityError — it would (rarely)
    create two active conversations instead, a different, lower-severity
    issue out of this sprint's scope."""
    conversation = db.scalars(
        select(Conversation)
        .where(
            Conversation.business_id == business_id,
            Conversation.customer_id == customer_id,
            Conversation.status == "active",
        )
        .order_by(Conversation.last_message_at.desc().nullslast())
    ).first()
    if conversation is None:
        conversation = Conversation(
            business_id=business_id, customer_id=customer_id, status="active"
        )
        db.add(conversation)
        db.flush()
    return conversation
