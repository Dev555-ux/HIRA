"""Background processing of inbound messages.

Runs after the webhook has acknowledged (so Meta isn't kept waiting): loads the
conversation, generates a grounded reply via the orchestrator, and stores it as
one or more outbound messages (Sprint 74 Phase 1: up to two, one per proposed
employee action — see app/ai/tools.py::response_to_message_fields) in
`pending_approval` status (Assisted Mode — a human approves before any of them
is actually sent, or before a proposed calendar/CRM action executes — see
DEC-032). Sending/executing is a separate, later step.

Two entry points, one shared implementation (Critical audit fix #3):

- `generate_and_store_reply` — the legacy, self-contained caller. Opens its
  own DB session because it runs outside any request/job lifecycle (the
  BackgroundTasks path, app/webhooks/whatsapp.py, when
  `settings.use_transactional_outbox` is off). Owns its transaction end to
  end, exactly as before this fix.
- `generate_reply_into_session` — writes through a *caller-supplied* session
  and never commits, rolls back, or closes it. This is what
  app/ai/tasks.py::handle_generate_ai_reply calls, so that a customer turn's
  writes (Messages, any tool execution, the ExecutionTrace) and the
  JobOutbox row's COMPLETED status are one atomic unit owned entirely by
  app/jobs/worker.py::OutboxWorker — see that module's docstring for why a
  handler previously opening its own independent session made zombie-sweep
  replay unsafe (a crash between that inner commit and the worker's own
  could re-run the whole turn from scratch).

  Idempotent by `trigger_message_id`: see this function's own docstring.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.intent import ConversationCategory
from app.ai.llm.base import LLMResponse, ToolCall
from app.ai.orchestrator import generate_reply
from app.ai.plan import ExecutionPlan
from app.ai.prompts import SYSTEM_PROMPT_VERSION
from app.ai.roles import RECEPTIONIST, role_for_tool
from app.ai.tools import confirmation_message_for, execute_tool_call, response_to_message_fields
from app.db.session import SessionLocal
from app.models import Business, Conversation, Customer, Escalation, ExecutionTrace, Message
from app.services.execution_traces import get_pending_action, record_execution_trace
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

# Sprint 77: Autonomous Mode previously left the customer with total silence
# when a proposed action (e.g. a calendar booking) failed to execute — see
# _auto_send's tool-call-failure branch. This replaces that silence with an
# honest, non-technical acknowledgment — never the tool's own internal
# failure reason (e.g. "This business has not connected a Google Calendar"),
# which is an operational detail for the founder, not the customer.
AUTONOMOUS_TOOL_FAILURE_TEXT = (
    "I wasn't able to complete that automatically, so I've flagged it for the team — "
    "they'll follow up with you shortly."
)


def generate_and_store_reply(
    conversation_id: uuid.UUID,
    trigger_message_id: uuid.UUID | None,
    user_text: str,
    *,
    sender: Callable[..., str] = send_text,
) -> None:
    """Self-contained entry point: opens its own session, owns commit/
    rollback/close end to end. Used by the legacy BackgroundTasks path
    (app/webhooks/whatsapp.py) when the transactional outbox is off — see
    this module's own docstring for the worker-owned-session counterpart.
    """
    db = SessionLocal()
    try:
        try:
            on_commit_failures = generate_reply_into_session(
                db, conversation_id, trigger_message_id, user_text, sender=sender
            )
        except Exception:
            logger.exception("Failed to generate reply for conversation %s", conversation_id)
            db.rollback()
            try:
                _store_failure_escalation(db, conversation_id)
                db.commit()
            except Exception:
                logger.exception(
                    "Failed to record fallback escalation for conversation %s", conversation_id
                )
                db.rollback()
            return

        # Section A4: each _auto_send call inside generate_reply_into_session
        # ran its tool call with commit=False, so its effect (e.g. an
        # Appointment row) is only flushed. This single commit is what
        # durably persists every message from this turn together with every
        # tool call's effect — all land or none does. On failure, every
        # collected on_commit_failure runs (in order) to delete now-orphaned
        # external side effects (e.g. calendar events) before re-raising.
        try:
            db.commit()
        except Exception:
            logger.exception("Failed to generate reply for conversation %s", conversation_id)
            for on_commit_failure in on_commit_failures:
                on_commit_failure()
            db.rollback()
            try:
                _store_failure_escalation(db, conversation_id)
                db.commit()
            except Exception:
                logger.exception(
                    "Failed to record fallback escalation for conversation %s", conversation_id
                )
                db.rollback()
            return
        # Deliberately generic: generate_reply_into_session already logs the
        # specific outcome (a prepared reply, an idempotent-replay skip, or
        # an LLM-failure escalation) at the point it happens — this is only
        # the "and it's now durably committed" confirmation, not a claim
        # about which of those outcomes this particular call was.
        logger.info("Committed reply-generation turn for conversation %s", conversation_id)
    finally:
        db.close()


def generate_reply_into_session(
    db: Session,
    conversation_id: uuid.UUID,
    trigger_message_id: uuid.UUID | None,
    user_text: str,
    *,
    sender: Callable[..., str] = send_text,
) -> list[Callable[[], None]]:
    """Do one customer turn's work through `db` — never commits, rolls back,
    or closes it; the caller owns that transaction boundary (Critical audit
    fix #3, Part B). app/jobs/worker.py::OutboxWorker calls this via
    app/ai/tasks.py::handle_generate_ai_reply with its own per-job session,
    so the turn's writes (Messages, any tool execution, the
    ExecutionTrace) and the job's COMPLETED status commit together as one
    atomic unit — the worker's `_process_job` does that single commit, not
    this function. `generate_and_store_reply` above is the other caller,
    for contexts with no session of their own to hand in.

    Idempotent by `trigger_message_id` (Part C): if an ExecutionTrace
    already exists for it, some earlier attempt at this exact turn already
    ran to completion and committed — record_execution_trace() is always
    the last write of a turn, in the same transaction as every Message and
    tool-execution write that turn produced, so its presence is proof the
    whole turn landed atomically, not just a partial attempt. This makes a
    zombie-recovery replay (or a retried job, for any reason) a safe no-op:
    it returns immediately, writing nothing, so the caller's commit has
    nothing new to persist and the job is correctly marked COMPLETED again
    for work that was, in fact, already done. `uq_execution_traces_
    trigger_message_id` (a partial unique index, app/models.py) backs this
    query efficiently and is the actual DB-enforced backstop if two
    attempts ever raced past this check concurrently — the second one's
    trace insert would fail the uniqueness check at commit time rather than
    silently duplicating.

    Only consulted when `trigger_message_id` is not None: tests (and any
    future non-webhook-triggered turn) legitimately pass None for "no
    specific trigger," and those must never be treated as duplicates of one
    another.

    Returns the on_commit_failure compensations (Section A4) the caller
    must invoke, in order, if *its own* commit of this work fails.
    """
    if trigger_message_id is not None:
        already_processed = (
            db.scalars(
                select(ExecutionTrace.id).where(
                    ExecutionTrace.trigger_message_id == trigger_message_id
                )
            ).first()
            is not None
        )
        if already_processed:
            logger.info(
                "Skipping reply generation for trigger_message_id=%s: an ExecutionTrace "
                "already exists (idempotent replay — a prior attempt already completed "
                "this turn)",
                trigger_message_id,
            )
            return []

    conversation = db.get(Conversation, conversation_id)
    if conversation is None:
        logger.warning("Conversation %s not found; skipping reply", conversation_id)
        return []

    # REL-2: a failure here (the LLM call itself) is the one this sprint's
    # fallback covers — nothing has been written yet (generate_reply() is
    # reads plus one LLM call), so a rollback is a safe, purely defensive
    # reset (recovering the session from any DB-error-induced state a
    # failed read may have left it in), never a discard of real work — even
    # under worker ownership, there is nothing else pending in this job's
    # transaction yet to lose. The resulting escalation write is left for
    # the caller to commit, same as every other write in this function.
    if user_text.strip():
        start = time.monotonic()
        try:
            response, retrieved, plan = generate_reply(db, conversation, user_text)
        except Exception:
            logger.exception("Failed to generate reply for conversation %s", conversation_id)
            db.rollback()
            _store_failure_escalation(db, conversation_id)
            return []
        duration_ms = int((time.monotonic() - start) * 1000)
    else:
        response, retrieved = LLMResponse(text=NON_TEXT_FALLBACK_TEXT, model="none"), []
        plan = ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())
        duration_ms = 0

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
            if message.ai_meta.get("failure_reason"):
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
                #
                # Sprint 77: checked via ai_meta["failure_reason"], not
                # message.status — a failed action can still end with
                # status == "sent" once its honest fallback text goes
                # out (see _auto_send), so status alone no longer says
                # whether the turn's actual request succeeded.
                _escalate_automation_failure(db, conversation)
                break

    # Sprint 76: recorded defensively — a tracing bug must never break
    # the real reply flow this loop just built. Flushed (not committed)
    # here so it lands atomically with this turn's Message rows in the
    # caller's single commit. Also the idempotency proof above (Part C)
    # — see this function's own docstring.
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
        logger.exception("Failed to record execution trace for conversation %s", conversation_id)

    logger.info(
        "Prepared reply for conversation %s (status=%s)",
        conversation_id,
        last_message.status if last_message else None,
    )
    return on_commit_failures


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

    Adds and flushes only — never commits (Critical audit fix #3, Part B):
    the caller (either generate_and_store_reply's own session, or, via
    generate_reply_into_session, a caller-owned one) commits this along
    with everything else in the same transaction.
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
    db.flush()


def _escalate_automation_failure(db, conversation: Conversation) -> None:
    """Sprint 77: an Autonomous Mode action failed for a reason the customer
    re-messaging can't fix (a missing setup step, an exhausted send retry,
    an expired service window...) — flags the conversation exactly like a
    human clicking Escalate would (app/services/replies.py::escalate_reply),
    so there's never a silent gap between "the customer got an honest
    fallback text, if one could be sent at all" and "someone at the business
    actually follows up." Unlike _store_failure_escalation, this doesn't
    commit on its own — it rides along in the caller's single outer commit,
    since (unlike a total generation failure) real work already happened
    this turn that needs to land atomically with it.
    """
    conversation.status = "escalated"
    db.add(
        Escalation(
            business_id=conversation.business_id,
            conversation_id=conversation.id,
            reason="automation_failed",
            status="open",
        )
    )


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

    Sprint 77: every failure branch sets message.ai_meta["failure_reason"] —
    the caller uses its *presence*, not message.status, as the "did the
    underlying action fail" signal. That distinction matters now: a failed
    tool call still ends with message.status == "sent" once its honest
    fallback text goes out (see the tool_call branch below), so status alone
    can no longer answer "did this turn's request actually succeed."
    message.status keeps meaning exactly what it always has — the delivery
    outcome of whatever body this row ends with.
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
        # Critical audit fix: no human reviews an Autonomous Mode send, so
        # the only legitimate way a governed tool (e.g. cancel_appointment)
        # may execute here is if *this* conversation already went through
        # governance's confirm-with-the-customer flow in a prior turn.
        # get_pending_action() re-reads the same state
        # app/ai/orchestrator.py::generate_reply() already consulted to
        # build this turn's plan — safe to read again here since nothing
        # writes a new trace for this turn until after this call returns
        # (see record_execution_trace below).
        result = execute_tool_call(
            db,
            business.id,
            tool_call,
            customer_id=customer.id,
            conversation_id=conversation.id,
            commit=False,
            pending_action=get_pending_action(db, conversation.id),
        )
        if result.success:
            message.ai_meta = {**message.ai_meta, "tool_result": result.message}
            # Section A1 fix: message.body up to this point is still
            # preview_tool_call()'s internal, dashboard-editable text (set at
            # creation in response_to_message_fields). Autonomous Mode has no
            # human to edit it before send, so it must never go out as-is.
            message.body = confirmation_message_for(tool_call, result)
            on_commit_failure = result.on_commit_failure
        else:
            # Sprint 77: previously returned here with no send attempted at
            # all — the customer got silence while a proposed action (e.g. a
            # calendar booking) silently failed. The WhatsApp channel itself
            # is fine here (unlike the two branches above), so there's no
            # reason not to tell the customer *something* happened — just
            # never the internal reason why: result.message can read like
            # "This business has not connected a Google Calendar", an
            # operational detail for the founder, not something a customer
            # should see. The real reason is preserved in ai_meta below for
            # the founder (and drives the escalation the caller creates).
            logger.warning(
                "Autonomous tool call %s failed for conversation %s: %s",
                tool_call.name,
                conversation.id,
                result.message,
            )
            message.ai_meta = {**message.ai_meta, "failure_reason": result.message}
            message.body = AUTONOMOUS_TOOL_FAILURE_TEXT
            on_commit_failure = None
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
        # Sprint 77: whatever this row's body was (a real confirmation, or
        # the honest fallback text above) never reached the customer either
        # way — escalate like any other failure. Preserves an existing
        # tool-failure reason if one's already set, rather than overwriting
        # it with the send failure and losing why the turn actually failed.
        message.status = "failed"
        message.ai_meta = {"failure_reason": "whatsapp_send_failed", **(message.ai_meta or {})}
        logger.exception("Autonomous send failed for conversation %s", conversation.id)

    return on_commit_failure
