"""WhatsApp (Meta Cloud API) webhook.

GET  /webhooks/whatsapp  — Meta subscription verification handshake.
POST /webhooks/whatsapp  — inbound messages. Verifies the HMAC signature,
dedupes by message id, persists the inbound message, and returns 200 quickly.

Heavy work (AI orchestration) is intentionally NOT done here yet — that is
dispatched later (S1-08+). The webhook's job is to authenticate, record, and
acknowledge fast so Meta does not retry.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.processing import generate_and_store_reply
from app.core.config import settings
from app.db.session import get_db
from app.models import Business, Conversation, Customer, Message

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

SERVICE_WINDOW = timedelta(hours=24)


def get_reply_dispatcher():
    """Returns the callable that schedules reply generation. Overridable in tests."""

    def dispatch(background_tasks: BackgroundTasks, conversation_id, user_text: str) -> None:
        # TEMPORARY DIAGNOSTIC — remove after debugging outbound send.
        print(f"[DIAG] dispatch() CALLED conversation_id={conversation_id}", flush=True)
        # TEMPORARY TIER-2 FALLBACK — only uncomment this pair of lines (and
        # comment out the add_task line below) if tier-1 diagnostics prove
        # dispatch() runs but generate_and_store_reply()'s first print still
        # never appears. That would isolate BackgroundTasks execution itself
        # as the failure point rather than anything upstream of dispatch().
        #     generate_and_store_reply(conversation_id, user_text)
        #     return
        background_tasks.add_task(generate_and_store_reply, conversation_id, user_text)
        print(f"[DIAG] dispatch() add_task() SCHEDULED conversation_id={conversation_id}", flush=True)

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


def _signature_valid(raw_body: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(settings.whatsapp_app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


@router.post("/whatsapp")
async def receive(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    dispatch=Depends(get_reply_dispatcher),
) -> Response:
    raw_body = await request.body()
    if not _signature_valid(raw_body, request.headers.get("X-Hub-Signature-256")):
        # TEMPORARY DIAGNOSTIC
        print("[DIAG] receive(): signature check FAILED -> 403 (nothing downstream runs)", flush=True)
        return Response(status_code=403)

    payload = await request.json()
    # TEMPORARY DIAGNOSTIC
    print(f"[DIAG] receive(): payload={payload}", flush=True)
    new_inbound = _persist_inbound(db, payload)
    # TEMPORARY DIAGNOSTIC
    print(f"[DIAG] receive(): new_inbound count={len(new_inbound)} value={new_inbound!r}", flush=True)
    for conversation_id, user_text in new_inbound:
        dispatch(background_tasks, conversation_id, user_text)
    # Always 200 once persisted, so Meta does not retry.
    return Response(status_code=200, content='{"status":"received"}', media_type="application/json")


def _persist_inbound(db: Session, payload: dict) -> list[tuple]:
    """Persist inbound messages; return (conversation_id, text) for new ones."""
    new_inbound: list[tuple] = []
    now = datetime.now(timezone.utc)
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            # Ignore delivery/status callbacks: they carry "statuses", not "messages".
            if not value.get("messages"):
                # TEMPORARY DIAGNOSTIC
                print(
                    f"[DIAG] _persist_inbound: no 'messages' key (value keys={list(value.keys())}) "
                    "-> skipping this change",
                    flush=True,
                )
                continue
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            business = db.scalars(
                select(Business).where(Business.whatsapp_phone_number_id == phone_number_id)
            ).first()
            # TEMPORARY DIAGNOSTIC
            print(
                f"[DIAG] _persist_inbound: phone_number_id={phone_number_id!r} "
                f"business_found={business is not None}",
                flush=True,
            )
            if business is None:
                continue  # unknown number — ignore gracefully

            names = {
                c.get("wa_id"): c.get("profile", {}).get("name") for c in value.get("contacts", [])
            }
            for msg in value.get("messages", []):
                wa_message_id = msg.get("id")
                already = db.scalars(
                    select(Message).where(Message.wa_message_id == wa_message_id)
                ).first()
                # TEMPORARY DIAGNOSTIC
                print(
                    f"[DIAG] _persist_inbound: wa_message_id={wa_message_id!r} "
                    f"already_exists={already is not None}",
                    flush=True,
                )
                if already is not None:
                    continue  # dedupe

                wa_phone = msg.get("from")
                customer = _get_or_create_customer(db, business.id, wa_phone, names.get(wa_phone))
                conversation = _get_or_create_conversation(db, business.id, customer.id, now)

                body = _extract_text(msg)
                db.add(
                    Message(
                        conversation_id=conversation.id,
                        business_id=business.id,
                        direction="inbound",
                        wa_message_id=wa_message_id,
                        body=body,
                        type=msg.get("type", "text"),
                        status="received",
                    )
                )
                conversation.last_message_at = now
                conversation.window_expires_at = now + SERVICE_WINDOW
                new_inbound.append((conversation.id, body))
                # TEMPORARY DIAGNOSTIC
                print(f"[DIAG] _persist_inbound: appended conversation_id={conversation.id}", flush=True)
            db.commit()
    return new_inbound


def _extract_text(msg: dict) -> str:
    if msg.get("type") == "text":
        return msg.get("text", {}).get("body", "")
    return ""


def _get_or_create_customer(
    db: Session, business_id, wa_phone: str, display_name: str | None
) -> Customer:
    customer = db.scalars(
        select(Customer).where(Customer.business_id == business_id, Customer.wa_phone == wa_phone)
    ).first()
    if customer is None:
        customer = Customer(business_id=business_id, wa_phone=wa_phone, display_name=display_name)
        db.add(customer)
        db.flush()
    return customer


def _get_or_create_conversation(db: Session, business_id, customer_id, now) -> Conversation:
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
