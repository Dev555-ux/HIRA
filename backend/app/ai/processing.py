"""Background processing of inbound messages.

Runs after the webhook has acknowledged (so Meta isn't kept waiting): loads the
conversation, generates a grounded reply via the orchestrator, and stores it as
one or more outbound messages (Sprint 74 Phase 1: up to two, one per proposed
employee action — see app/ai/tools.py::response_to_message_fields) in
`pending_approval` status (Assisted Mode — a human approves before any of them
is actually sent, or before a proposed calendar/CRM action executes — see
DEC-032). Sending/executing is a separate, later step.

Opens its own DB session because it runs outside the request lifecycle.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from app.ai.intent import ConversationCategory
from app.ai.llm.base import LLMResponse, ToolCall
from app.ai.orchestrator import generate_reply
from app.ai.plan import ExecutionPlan
from app.ai.prompts import SYSTEM_PROMPT_VERSION
from app.ai.roles import RECEPTIONIST, role_for_tool
from app.ai.tools import confirmation_message_for, execute_tool_call, response_to_message_fields
from app.db.session import SessionLocal
from app.models import Business, Conversation, Customer, Escalation, Message
from app.services.execution_traces import record_execution_trace
from app.services.messaging import WhatsAppSendError, send_text
from app.whatsapp.credentials import get_access_token, get_stored_credential

logger = logging.getLogger(__name__)

# AI-3: app/webhooks/whatsapp.py::_extract_text collapses any non-text
# inbound message (image/audio/video/location/...) to "" — there is nothing
# for the LLM to ground a reply on. Rather than calling the orchestrator on
# an empty string (previously: an ungrounded, unpredictable reply) this is
# drafted directly, through the same pending_approval/auto-send pipeline a
# real AI reply goes through.
NON_TEXT_FALLBACK_TEXT = (
    "Thanks for your message! I can currently only read text — could you type that out for me?"
)


def generate_and_store_reply(
    conversation_id: uuid.UUID,
    trigger_message_id: uuid.UUID,
    user_text: str,
    *,
    sender: Callable[..., str] = send_text,
) -> None:
    db = SessionLocal()
    try:
        conversation = db.get(Conversation, conversation_id)
        if conversation is None:
            logger.warning("Conversation %s not found; skipping reply", conversation_id)
            return

        # REL-2: a failure here (the LLM call itself) is the one this sprint's
        # fallback covers — nothing has been written yet, so there's a clean
        # rollback + escalate. A failure *after* this point (send/commit) has
        # its own atomicity handling below (on_commit_failure) and is left to
        # the outer except unchanged, so it isn't double-escalated on top of
        # that already-tested compensation path.
        try:
            if user_text.strip():
                start = time.monotonic()
                response, retrieved, plan = generate_reply(db, conversation, user_text)
                duration_ms = int((time.monotonic() - start) * 1000)
            else:
                response, retrieved = LLMResponse(text=NON_TEXT_FALLBACK_TEXT, model="none"), []
                plan = ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())
                duration_ms = 0
        except Exception:
            logger.exception("Failed to generate reply for conversation %s", conversation_id)
            db.rollback()
            try:
                _store_failure_escalation(db, conversation_id)
            except Exception:
                logger.exception(
                    "Failed to record fallback escalation for conversation %s", conversation_id
                )
                db.rollback()
            return

        business = db.get(Business, conversation.business_id)

        # Sprint 74 Phase 1 (DEC-043): response_to_message_fields() now
        # returns up to MAX_TOOL_CALLS_PER_TURN entries (still always at
        # least one) — each becomes its own independently governed,
        # independently auditable Message row, processed sequentially, in
        # order. A single-tool-call turn (the overwhelming common case,
        # and every case before this sprint) produces exactly the one
        # Message row it always did — this loop body is identical to the
        # old single-message code, just repeated 1-2 times instead of
        # written out once.
        on_commit_failures: list[Callable[[], None]] = []
        last_message: Message | None = None
        proposed_tool_calls: list[dict] = []
        result_message_ids: list[uuid.UUID] = []
        for message_type, body, extra_ai_meta in response_to_message_fields(response):
            tool_name = extra_ai_meta.get("tool_name")
            agent_role = role_for_tool(tool_name) if tool_name else RECEPTIONIST
            if tool_name:
                proposed_tool_calls.append({"tool_name": tool_name, "agent_role": agent_role})
            message = Message(
                conversation_id=conversation.id,
                business_id=conversation.business_id,
                direction="outbound",
                body=body,
                type=message_type,
                status="pending_approval",
                ai_meta={
                    "model": response.model,
                    "prompt_version": SYSTEM_PROMPT_VERSION,
                    "retrieved_count": len(retrieved),
                    "agent_role": agent_role,
                    **extra_ai_meta,
                },
            )
            db.add(message)
            db.flush()
            last_message = message
            result_message_ids.append(message.id)

            # Autonomous Mode: send/execute immediately with no human
            # approval. Assisted Mode (the default) leaves the reply/
            # proposed action as pending_approval for the dashboard.
            if business is not None and business.mode == "autonomous":
                on_commit_failure = _auto_send(db, business, conversation, message, sender)
                if on_commit_failure is not None:
                    on_commit_failures.append(on_commit_failure)
                if message.status == "failed":
                    # Sprint 75, Objective D: stop execution — a later
                    # planned action may have been proposed on the
                    # assumption this one succeeded (e.g. "reschedule to
                    # Thursday, then log the new contact info"), so
                    # proceeding after a failure risks acting on a false
                    # premise. Whatever this turn already sent (if
                    # anything, from an earlier successful step) stands as
                    # the safe partial response; the failed step is marked
                    # and fully auditable, same as a single-action failure
                    # always was — just no longer followed by more actions.
                    break

        # Sprint 76: recorded defensively — a tracing bug must never break
        # the real reply flow this loop just built. Flushed (not committed)
        # here so it lands atomically with this turn's Message rows in the
        # single commit below.
        try:
            record_execution_trace(
                db,
                business_id=conversation.business_id,
                conversation_id=conversation.id,
                trigger_message_id=trigger_message_id,
                plan=plan,
                proposed_tool_calls=proposed_tool_calls,
                result_message_ids=result_message_ids,
                duration_ms=duration_ms,
            )
        except Exception:
            logger.exception(
                "Failed to record execution trace for conversation %s", conversation_id
            )

        # Section A4: each _auto_send call above ran its tool call with
        # commit=False, so its effect (e.g. an Appointment row) is only
        # flushed. This single commit is what durably persists every
        # message from this turn together with every tool call's effect —
        # all land or none does. On failure, every collected
        # on_commit_failure runs (in order) to delete now-orphaned external
        # side effects (e.g. calendar events) before re-raising, to be
        # caught by the except below like any other failure here.
        try:
            db.commit()
        except Exception:
            for on_commit_failure in on_commit_failures:
                on_commit_failure()
            raise
        logger.info(
            "Stored reply for conversation %s (status=%s)",
            conversation_id,
            last_message.status if last_message else None,
        )
    except Exception:
        logger.exception("Failed to generate reply for conversation %s", conversation_id)
        db.rollback()
    finally:
        db.close()


def _store_failure_escalation(db, conversation_id: uuid.UUID) -> None:
    """REL-2: on an AI generation failure, the old behavior left zero trace —
    no Message row, no signal anywhere a human would look, customer met with
    silence. This reuses the exact mechanism a human already uses to flag a
    conversation (app/services/replies.py::escalate_reply — same "escalated"
    Message/Conversation status, same Escalation row, already rendered by the
    dashboard's Inbox), just triggered by a system failure instead of a
    person clicking Escalate. reason="external_failure" is one of
    Escalation.reason's existing documented values (app/models.py), not a
    new one invented for this.
    """
    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        return
    message = Message(
        conversation_id=conversation.id,
        business_id=conversation.business_id,
        direction="outbound",
        body=(
            "HIRA couldn't generate a reply to this message due to a temporary issue. "
            "This conversation has been flagged for you to follow up manually."
        ),
        type="text",
        status="escalated",
    )
    db.add(message)
    conversation.status = "escalated"
    db.add(
        Escalation(
            business_id=conversation.business_id,
            conversation_id=conversation.id,
            reason="external_failure",
            status="open",
        )
    )
    db.commit()


def _auto_send(
    db,
    business: Business,
    conversation: Conversation,
    message: Message,
    sender: Callable[..., str],
) -> Callable[[], None] | None:
    """Send/execute the reply immediately (Autonomous Mode) and mark sent/failed.

    For a proposed calendar action (message.type == "tool_call"), the tool
    executes first — no approval gate in this mode, mirroring how a text
    reply already sends immediately here (DEC-027, extended by DEC-032).

    Runs the tool with commit=False (Section A4) and returns the resulting
    `on_commit_failure` (or None) so the caller's single outer commit can
    compensate if it fails — see generate_and_store_reply.

    Sprint 69: checked up front, before any tool call — no WhatsApp
    connection (phone number or stored credential) or an expired 24-hour
    service window both mean there's no way to notify the customer, so
    nothing here should proceed far enough to need reverting. Mirrors
    app/services/replies.py::approve_and_send's identical up-front checks.
    """
    customer = db.get(Customer, conversation.customer_id)
    credential = get_stored_credential(db, business.id)

    if not business.whatsapp_phone_number_id or credential is None:
        message.status = "failed"
        message.ai_meta = {**(message.ai_meta or {}), "failure_reason": "whatsapp_not_connected"}
        logger.warning(
            "Autonomous send skipped for conversation %s: WhatsApp not connected", conversation.id
        )
        return None

    if (
        conversation.window_expires_at is not None
        and datetime.now(timezone.utc).replace(tzinfo=None) > conversation.window_expires_at
    ):
        message.status = "failed"
        message.ai_meta = {**(message.ai_meta or {}), "failure_reason": "whatsapp_window_expired"}
        logger.warning(
            "Autonomous send skipped for conversation %s: WhatsApp 24h service window expired",
            conversation.id,
        )
        return None

    if message.type == "tool_call":
        tool_call = ToolCall(
            id="autonomous",
            name=message.ai_meta["tool_name"],
            arguments=message.ai_meta["tool_arguments"],
        )
        result = execute_tool_call(
            db,
            business.id,
            tool_call,
            customer_id=customer.id,
            conversation_id=conversation.id,
            commit=False,
        )
        if not result.success:
            message.status = "failed"
            logger.warning(
                "Autonomous tool call %s failed for conversation %s: %s",
                tool_call.name,
                conversation.id,
                result.message,
            )
            return None
        message.ai_meta = {**message.ai_meta, "tool_result": result.message}
        # Section A1 fix: message.body up to this point is still
        # preview_tool_call()'s internal, dashboard-editable text (set at
        # creation in response_to_message_fields). Autonomous Mode has no
        # human to edit it before send, so it must never go out as-is.
        message.body = confirmation_message_for(tool_call, result)
        on_commit_failure = result.on_commit_failure
    else:
        on_commit_failure = None

    try:
        wa_message_id = sender(
            business.whatsapp_phone_number_id,
            customer.wa_phone,
            message.body,
            access_token=get_access_token(credential),
        )
        message.status = "sent"
        message.wa_message_id = wa_message_id
        logger.info("Autonomously sent reply for conversation %s", conversation.id)
    except WhatsAppSendError:
        message.status = "failed"
        logger.exception("Autonomous send failed for conversation %s", conversation.id)

    return on_commit_failure
