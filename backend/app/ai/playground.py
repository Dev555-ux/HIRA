"""Demo Chat (formerly "Playground") — a second transport onto the exact same
AI pipeline WhatsApp uses.

Reuses the production reply pipeline exactly: `orchestrator.generate_reply()`
is called unmodified, so retrieval, prompt building, and the Groq/Claude LLM
call are never duplicated here. See ONBOARDING_ARCHITECTURE.md §4.4.

One synthetic Customer/Conversation per business (`wa_phone="__playground__"`)
gives each turn real conversation history for free — the same
`_load_history()` the WhatsApp pipeline already uses, not a parallel one.
Turns are persisted as ordinary `Message` rows so that history works, and a
proposed tool call (a booking, a lead) executes for real via the exact same
`execute_tool_call()`/`confirmation_message_for()` Autonomous Mode's
`_auto_send` already uses (app/ai/processing.py) — there is no real customer
or human reviewer on the other end of a demo conversation, so the
Assisted-Mode approval gate would only ever be a dead end here, same
reasoning `_auto_send` already applies to Autonomous Mode.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm import LLMError, LLMResponse
from app.ai.llm.base import ToolCall
from app.ai.orchestrator import generate_reply
from app.ai.tools import confirmation_message_for, execute_tool_call, response_to_message_fields
from app.models import Conversation, Customer, KbEntry, Message

logger = logging.getLogger(__name__)

PLAYGROUND_PHONE = "__playground__"

# Customer-visible fallback when the LLM provider itself fails (e.g. Groq's
# tool_use_failed 400 on a malformed function call — app/api/dashboard.py's
# regenerate endpoint hits the same LLMError and already treats it as a
# normal, expected failure mode rather than a crash: see its `except
# LLMError` there). Demo Chat has no Pending queue to fall back to (there's
# no human reviewer on a demo conversation), so unlike that endpoint this
# can't just return an HTTP error — the chat UI has nothing to render for a
# failed request except an error banner. Resolving it into an ordinary
# assistant turn instead means the conversation stays usable and the turn is
# preserved in history, same as any other reply.
LLM_UNAVAILABLE_TEXT = (
    "I'm having trouble completing that right now — please try again in a moment."
)


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
            business_id=business_id, wa_phone=PLAYGROUND_PHONE, display_name="Demo Chat"
        )
        db.add(customer)
        db.flush()

    conversation = db.scalars(
        select(Conversation).where(
            Conversation.business_id == business_id, Conversation.customer_id == customer.id
        )
    ).first()
    if conversation is None:
        conversation = Conversation(
            business_id=business_id, customer_id=customer.id, status="active"
        )
        db.add(conversation)
        db.flush()
    return conversation


def playground_reply(
    db: Session, business_id: uuid.UUID, user_text: str
) -> tuple[LLMResponse, list[KbEntry], str, dict | None]:
    """Run one Demo Chat turn through the unmodified production reply pipeline.

    Returns (response, retrieved_entries, body, tool_outcome). `retrieved_entries`
    is surfaced (not discarded) so the UI can show which Business Knowledge
    entries grounded the answer. `body` is the final, human-readable text
    actually stored/shown — if the model proposed a tool call, this is its
    *resolved* confirmation or failure text (see below), never the internal
    dashboard-editable preview `app/api/dashboard.py`'s Pending queue shows.
    `tool_outcome` is `{"name": str, "success": bool}` when a tool call was
    involved, else `None` — lets the UI show a small "✓ Lead logged" style
    note distinct from the chat bubble, without the frontend needing to know
    anything about tool internals.
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

    try:
        response, retrieved = generate_reply(db, conversation, user_text)
    except LLMError:
        logger.exception(
            "Demo Chat LLM call failed for business %s; returning fallback reply", business_id
        )
        response = LLMResponse(text=LLM_UNAVAILABLE_TEXT, model="unavailable")
        retrieved = []
    message_type, body, extra_ai_meta = response_to_message_fields(response)
    ai_meta = {"model": response.model, "retrieved_count": len(retrieved), **extra_ai_meta}

    tool_outcome: dict | None = None
    if message_type == "tool_call":
        # Demo Chat executes proposed actions immediately rather than holding
        # them in the Pending Approvals queue — there is no real customer or
        # human reviewer waiting on a demo conversation, so "pending approval"
        # here would just be a permanent dead end. Reuses the exact same
        # execute_tool_call()/confirmation_message_for() Autonomous Mode's
        # _auto_send already calls (app/ai/processing.py) — no new execution
        # path, no bypass of the tool layer.
        tool_call = ToolCall(
            id="demo", name=extra_ai_meta["tool_name"], arguments=extra_ai_meta["tool_arguments"]
        )
        result = execute_tool_call(
            db, business_id, tool_call,
            customer_id=conversation.customer_id,
            conversation_id=conversation.id,
        )
        ai_meta["tool_result"] = result.message
        tool_outcome = {"name": tool_call.name, "success": result.success}
        # Either way, the customer-visible text is a resolved outcome, never
        # the Pending queue's internal "Book: ..." editable preview (Section
        # A1's same fix, applied here) — success gets the deterministic
        # confirmation text; failure gets the tool's own honest reason (e.g.
        # "This business has not connected a Google Calendar").
        message_type = "text"
        body = confirmation_message_for(tool_call, result) if result.success else result.message

    outbound = Message(
        conversation_id=conversation.id,
        business_id=business_id,
        direction="outbound",
        body=body,
        type=message_type,
        status="sent",
        ai_meta=ai_meta,
    )
    db.add(outbound)
    db.commit()

    return response, retrieved, body, tool_outcome
