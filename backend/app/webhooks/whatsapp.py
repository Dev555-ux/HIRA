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

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import Business, Conversation, Customer, Message

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

SERVICE_WINDOW = timedelta(hours=24)


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
async def receive(request: Request, db: Session = Depends(get_db)) -> Response:
    raw_body = await request.body()
    if not _signature_valid(raw_body, request.headers.get("X-Hub-Signature-256")):
        return Response(status_code=403)

    payload = await request.json()
    _persist_inbound(db, payload)
    # Always 200 once persisted, so Meta does not retry.
    return Response(status_code=200, content='{"status":"received"}', media_type="application/json")


def _persist_inbound(db: Session, payload: dict) -> None:
    now = datetime.now(timezone.utc)
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            business = db.scalars(
                select(Business).where(Business.whatsapp_phone_number_id == phone_number_id)
            ).first()
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
                if already is not None:
                    continue  # dedupe

                wa_phone = msg.get("from")
                customer = _get_or_create_customer(db, business.id, wa_phone, names.get(wa_phone))
                conversation = _get_or_create_conversation(db, business.id, customer.id, now)

                db.add(
                    Message(
                        conversation_id=conversation.id,
                        business_id=business.id,
                        direction="inbound",
                        wa_message_id=wa_message_id,
                        body=_extract_text(msg),
                        type=msg.get("type", "text"),
                        status="received",
                    )
                )
                conversation.last_message_at = now
                conversation.window_expires_at = now + SERVICE_WINDOW
            db.commit()


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
