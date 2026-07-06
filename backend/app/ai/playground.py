"""AI Playground — a synchronous test-drive of the AI receptionist.

Reuses the production reply pipeline exactly: `orchestrator.generate_reply()`
is called unmodified, so retrieval, prompt building, and the Groq/Claude LLM
call are never duplicated here. See ONBOARDING_ARCHITECTURE.md §4.4.

One synthetic Customer/Conversation per business (`wa_phone="__playground__"`)
gives each playground turn real conversation history for free — the same
`_load_history()` the WhatsApp pipeline already uses, not a parallel one.
Turns are persisted as ordinary `Message` rows so that history works, but the
outbound message is marked `sent` immediately: there is no real customer
waiting, so the Assisted-Mode approval gate does not apply here.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm import LLMResponse
from app.ai.orchestrator import generate_reply
from app.models import Conversation, Customer, KbEntry, Message

PLAYGROUND_PHONE = "__playground__"


def get_or_create_playground_conversation(db: Session, business_id: uuid.UUID) -> Conversation:
    """One persistent synthetic conversation per business for test-drive turns.

    Excluded from real inbox/analytics by the marker phone number — any future
    query over real customer conversations filters `wa_phone != "__playground__"`.
    """
    customer = db.scalars(
        select(Customer).where(
            Customer.business_id == business_id, Customer.wa_phone == PLAYGROUND_PHONE
        )
    ).first()
    if customer is None:
        customer = Customer(
            business_id=business_id, wa_phone=PLAYGROUND_PHONE, display_name="Playground"
        )
        db.add(customer)
        db.flush()

    conversation = db.scalars(
        select(Conversation).where(
            Conversation.business_id == business_id, Conversation.customer_id == customer.id
        )
    ).first()
    if conversation is None:
        conversation = Conversation(business_id=business_id, customer_id=customer.id, status="active")
        db.add(conversation)
        db.flush()
    return conversation


def playground_reply(
    db: Session, business_id: uuid.UUID, user_text: str
) -> tuple[LLMResponse, list[KbEntry]]:
    """Run one playground turn through the unmodified production reply pipeline.

    Returns (response, retrieved_entries) — unlike the architecture doc's
    sketch, the retrieved entries are surfaced (not discarded) so the
    Playground UI can show which Knowledge Base entries grounded the answer.
    """
    conversation = get_or_create_playground_conversation(db, business_id)

    inbound = Message(
        conversation_id=conversation.id,
        business_id=business_id,
        direction="inbound",
        body=user_text,
        type="text",
        status="received",
    )
    db.add(inbound)
    db.flush()

    response, retrieved = generate_reply(db, conversation, user_text)

    outbound = Message(
        conversation_id=conversation.id,
        business_id=business_id,
        direction="outbound",
        body=response.text,
        type="text",
        status="sent",
        ai_meta={"model": response.model, "retrieved_count": len(retrieved)},
    )
    db.add(outbound)
    db.commit()

    return response, retrieved
