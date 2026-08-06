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
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.intent import ConversationCategory
from app.ai.llm import LLMError, LLMResponse
from app.ai.llm.base import ToolCall
from app.ai.orchestrator import generate_reply
from app.ai.plan import ExecutionPlan
from app.ai.roles import RECEPTIONIST, role_for_tool
from app.ai.tools import confirmation_message_for, execute_tool_call, response_to_message_fields
from app.models import Conversation, Customer, KbEntry, Message
from app.services.execution_traces import get_pending_action, record_execution_trace

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

    start = time.monotonic()
    try:
        response, retrieved, plan = generate_reply(db, conversation, user_text)
    except LLMError as exc:
        logger.exception(
            "Demo Chat LLM call failed for business %s; returning fallback reply", business_id
        )
        response = LLMResponse(text=LLM_UNAVAILABLE_TEXT, model="unavailable")
        retrieved = []
        # Sprint 80 follow-up: if generate_reply() got as far as computing a
        # real plan before the LLM call itself failed, app/ai/orchestrator.py
        # attaches it as exc.plan — use that so the trace still shows what
        # was actually offered this turn (e.g. action/scheduler/4 tools)
        # instead of always downgrading to an empty "conversation" plan,
        # which was misleading Founder Ops on exactly the turns where an
        # accurate trace mattered most.
        plan = getattr(exc, "plan", None) or ExecutionPlan(
            category=ConversationCategory.CONVERSATION, steps=()
        )
    duration_ms = int((time.monotonic() - start) * 1000)

    # Sprint 74 Phase 1 (DEC-043): up to MAX_TOOL_CALLS_PER_TURN entries now,
    # each executed immediately and persisted as its own Message — same
    # reasoning as before (no human reviewer on a demo conversation, so
    # holding anything as pending_approval would be a dead end), just
    # repeated sequentially instead of written out once. The API/UI contract
    # is intentionally unchanged (still one `body`/`tool_outcome` returned,
    # from the *last* entry) — Demo Chat's frontend shows one reply bubble
    # per turn; earlier entries are still fully persisted and attributed,
    # just not the one reflected in this return value. See
    # documentation/API.md if a future sprint wants to surface all of them.
    last_body = ""
    last_tool_outcome: dict | None = None
    proposed_tool_calls: list[dict] = []
    result_message_ids: list[uuid.UUID] = []
    for message_type, body, extra_ai_meta in response_to_message_fields(response):
        tool_name = extra_ai_meta.get("tool_name")
        agent_role = role_for_tool(tool_name) if tool_name else RECEPTIONIST
        if tool_name:
            proposed_tool_calls.append({"tool_name": tool_name, "agent_role": agent_role})
        ai_meta = {
            "model": response.model,
            "retrieved_count": len(retrieved),
            "agent_role": agent_role,
            **extra_ai_meta,
        }

        tool_outcome: dict | None = None
        if message_type == "tool_call":
            # Demo Chat executes proposed actions immediately rather than
            # holding them in the Pending Approvals queue — reuses the exact
            # same execute_tool_call()/confirmation_message_for() Autonomous
            # Mode's _auto_send already calls (app/ai/processing.py) — no
            # new execution path, no bypass of the tool layer.
            tool_call = ToolCall(
                id="demo",
                name=extra_ai_meta["tool_name"],
                arguments=extra_ai_meta["tool_arguments"],
            )
            # Critical audit fix: Demo Chat has no human reviewer either (see
            # this module's docstring), so it needs the same confirmation
            # proof Autonomous Mode's _auto_send provides — see
            # app/ai/processing.py for the full reasoning.
            result = execute_tool_call(
                db,
                business_id,
                tool_call,
                customer_id=conversation.customer_id,
                conversation_id=conversation.id,
                pending_action=get_pending_action(db, conversation.id),
            )
            ai_meta["tool_result"] = result.message
            tool_outcome = {"name": tool_call.name, "success": result.success}
            # Either way, the customer-visible text is a resolved outcome,
            # never the Pending queue's internal "Book: ..." editable
            # preview (Section A1's same fix, applied here) — success gets
            # the deterministic confirmation text; failure gets the tool's
            # own honest reason (e.g. "This business has not connected a
            # Google Calendar").
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
        db.flush()
        last_body = body
        last_tool_outcome = tool_outcome
        result_message_ids.append(outbound.id)

        if tool_outcome is not None and not tool_outcome["success"]:
            # Sprint 75, Objective D: stop execution — same reasoning as
            # Autonomous Mode's identical check in app/ai/processing.py. A
            # later planned action may assume this one succeeded, so this
            # demo turn ends here rather than proposing further actions on
            # a false premise. What already sent (if anything from an
            # earlier successful step) stands as the safe partial reply.
            break

    # Sprint 76: same defensive recording as app/ai/processing.py — a
    # tracing bug must never break a demo turn's real reply.
    try:
        record_execution_trace(
            db,
            business_id=business_id,
            conversation_id=conversation.id,
            trigger_message_id=inbound.id,
            plan=plan,
            proposed_tool_calls=proposed_tool_calls,
            result_message_ids=result_message_ids,
            duration_ms=duration_ms,
        )
    except Exception:
        logger.exception("Failed to record execution trace for business %s", business_id)

    db.commit()

    return response, retrieved, last_body, last_tool_outcome
