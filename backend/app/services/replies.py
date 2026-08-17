"""Assisted-Mode draft management for a pending AI-drafted reply.

Assisted Mode stores AI-generated replies as outbound `pending_approval`
messages. This module holds every non-sending action a human can take on
one: edit, reject, regenerate, or escalate to a human. Approving and
sending it moved to `app.services.messaging_service.MessagingService.
approve_and_send()` in Sprint 64A PR 7 — see that method's docstring; it
is a relocation of this module's old `approve_and_send()`, not a rewrite.

Every function is tenant-scoped by `business_id` via `get_scoped`/
`get_pending_reply` and raises `ValueError` if the message doesn't exist,
belongs to another business, or is no longer an editable pending reply
(already sent, rejected, escalated, etc.) — the API layer turns that into
a 404, same as the original approve endpoint, so a wrong-tenant message
and a non-existent one look identical to the caller.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingProvider
from app.ai.llm import LLMProvider
from app.ai.orchestrator import generate_reply
from app.ai.prompts import SYSTEM_PROMPT_VERSION
from app.ai.roles import RECEPTIONIST, role_for_tool
from app.ai.tools import response_to_message_fields
from app.core.config import settings
from app.db.tenant import get_scoped
from app.models import Conversation, Escalation, Message

logger = logging.getLogger(__name__)


def get_pending_reply(db: Session, business_id: uuid.UUID, message_id: uuid.UUID) -> Message:
    """Fetch a message, but only if it's this business's editable pending
    reply. Public (no longer `_get_pending_reply`) as of Sprint 64A PR 7:
    `MessagingService.approve_and_send()` needs it too — same convention
    as `signature_valid`'s PR 4 relocation, a name only needs to be
    private until a second module genuinely needs it."""
    message = get_scoped(db, Message, business_id, message_id)
    if message is None or message.direction != "outbound" or message.status != "pending_approval":
        raise ValueError("Message is not a pending reply for this business")
    return message


def update_draft(
    db: Session,
    business_id: uuid.UUID,
    message_id: uuid.UUID,
    *,
    body: str,
) -> Message:
    """Edit a pending AI draft's text before approval.

    Raises ValueError if the message isn't an editable pending reply for this
    business (including if it has already been approved/sent).
    """
    message = get_pending_reply(db, business_id, message_id)
    message.body = body
    db.commit()
    logger.info("Edited draft %s for business %s", message_id, business_id)
    return message


def reject_reply(db: Session, business_id: uuid.UUID, message_id: uuid.UUID) -> Message:
    """Reject a pending reply: it is removed from the pending queue and never sent.

    Raises ValueError if the message isn't a pending reply for this business.
    """
    message = get_pending_reply(db, business_id, message_id)
    message.status = "rejected"
    db.commit()
    logger.info("Rejected reply %s for business %s", message_id, business_id)
    return message


def _last_inbound_before(db: Session, conversation_id: uuid.UUID, before) -> Message | None:
    """The most recent customer message up to a given timestamp in a conversation.

    Uses <= rather than < because Postgres's `now()` (used for `created_at`'s
    server default) is fixed for the duration of a transaction — an inbound
    message and the outbound draft it triggered can legitimately share the same
    timestamp if both were written without an intervening commit. Safe to
    include ties here since this is already filtered to `direction == "inbound"`,
    so it can never match the (outbound) draft itself.
    """
    return db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conversation_id,
            Message.direction == "inbound",
            Message.created_at <= before,
        )
        .order_by(Message.created_at.desc())
    ).first()


def regenerate_draft(
    db: Session,
    business_id: uuid.UUID,
    message_id: uuid.UUID,
    *,
    llm: LLMProvider | None = None,
    embedding: EmbeddingProvider | None = None,
) -> Message:
    """Regenerate a pending draft's text via the unmodified `generate_reply` pipeline.

    Replaces only this message's body/ai_meta — conversation history and the
    approval workflow are untouched. Raises ValueError if the message isn't a
    pending reply for this business, or if there's no customer message left to
    respond to (the draft's own inbound trigger message would have to have been
    deleted, which nothing in the app does today).
    """
    message = get_pending_reply(db, business_id, message_id)
    conversation = db.get(Conversation, message.conversation_id)

    user_message = _last_inbound_before(db, conversation.id, message.created_at)
    if user_message is None:
        raise ValueError("No customer message found to regenerate a reply for")

    # The plan generate_reply() used isn't traced here — regenerate replaces
    # an existing Message in place rather than starting a new turn, and
    # Sprint 76 deliberately keeps this module untouched by execution
    # tracing (see app/services/execution_traces.py's docstring).
    response, retrieved, _plan = generate_reply(
        db, conversation, user_message.body, llm=llm, embedding=embedding
    )
    # Sprint 74 Phase 1 (DEC-043): response_to_message_fields() can return up
    # to two entries now, but regenerate replaces exactly one already-
    # existing Message in place — there's no second row to spawn here. Only
    # the first (primary) proposed action is used; a second action the model
    # proposed on regeneration is silently dropped, a deliberate, narrow
    # Phase 1 scope limit for this rare, explicit, human-triggered action
    # (not the primary path multi-action collaboration targets).
    message_type, body, extra_ai_meta = response_to_message_fields(response)[0]
    tool_name = extra_ai_meta.get("tool_name")
    message.type = message_type
    message.body = body
    message.ai_meta = {
        "model": response.model,
        "prompt_version": SYSTEM_PROMPT_VERSION,
        "retrieved_count": len(retrieved),
        "agent_role": role_for_tool(tool_name) if tool_name else RECEPTIONIST,
        "regenerated": True,
        **extra_ai_meta,
    }
    db.commit()
    logger.info("Regenerated draft %s for business %s", message_id, business_id)
    return message


def escalate_reply(
    db: Session,
    business_id: uuid.UUID,
    message_id: uuid.UUID,
    *,
    reason: str = "other",
) -> tuple[Message, Escalation]:
    """Escalate a pending reply to a human.

    Removes the message from the pending queue (status -> "escalated"), marks
    the conversation "escalated" (an existing, previously-unused Conversation
    status), and opens an Escalation row — conversation history is untouched.
    Raises ValueError if the message isn't a pending reply for this business.
    """
    message = get_pending_reply(db, business_id, message_id)
    conversation = db.get(Conversation, message.conversation_id)

    message.status = "escalated"
    conversation.status = "escalated"
    escalation = Escalation(
        business_id=business_id,
        conversation_id=conversation.id,
        reason=reason,
        status="open",
    )
    db.add(escalation)
    db.commit()
    db.refresh(escalation)
    logger.info("Escalated reply %s for business %s", message_id, business_id)
    return message, escalation


def recover_stale_sending_messages(
    db: Session,
    *,
    timeout_seconds: int | None = None,
    batch_size: int = 500,
) -> int:
    """Critical audit fix #2, Part D: return Messages stuck in "sending" past
    `timeout_seconds` (default `settings.stale_sending_message_timeout_seconds`)
    to a terminal state. Meant to run periodically from a long-running worker
    process (see app/jobs/worker.py::OutboxWorker.run_once, which calls this
    every poll cycle alongside its own recover_zombies() — the same
    "scheduled sweep inside an already-running process" shape, reused rather
    than standing up a second scheduling mechanism for one more cleanup job).

    Why this is still needed after approve_and_send()'s own broadened
    exception handling (Part B above): that fix guarantees every *live*
    approve_and_send() call resolves "sending" to a terminal status before
    returning, including on an unexpected exception. It cannot guarantee
    anything about a process that's killed outright (OOM, a host failure, a
    deploy that SIGKILLs mid-request) — nothing raises in that case for any
    exception handler to catch. This sweep is the backstop for exactly that
    residual case, the same relationship app/jobs/worker.py's zombie sweep
    has to its own per-job exception handling.

    Query shape mirrors OutboxWorker.recover_zombies(): a partial index
    (app/models.py's ix_messages_sending_updated, on (status, updated_at)
    WHERE status='sending') keeps this a small, targeted scan regardless of
    how large the messages table grows, and `FOR UPDATE SKIP LOCKED` makes
    it safe to run from more than one worker process at once — two
    concurrent sweeps split the stale set instead of double-processing any
    one row. `batch_size` bounds how much work one call takes on, so a
    worker loop calling this every poll cycle never stalls behind an
    unusually large backlog.

    Idempotent by construction: recovering a message changes its status
    away from "sending", so it simply won't be selected by a later call —
    there is no separate "already processed" flag to maintain, and no
    partial-recovery state a re-run could double-apply.

    Recovers to "failed", deliberately never back to "pending_approval":
    nothing in this module's approval flow (see execute_tool_call) guards
    against re-executing an already-executed tool call, so silently
    re-queuing for a human to re-approve would risk a duplicate
    booking/reschedule/cancellation if the original attempt's tool call had
    in fact already gone through before its process died. A message whose
    `type == "tool_call"` also gets an Escalation (reason="external_failure",
    an existing, documented Escalation.reason value — see app/models.py):
    this sweep has no way to confirm or rule out whether the tool's external
    side effect (e.g. a calendar booking) already happened before the crash
    — the local Appointment row it would have referenced was only flushed,
    never committed, so a crash mid-attempt leaves no local trace either
    way — so it surfaces that ambiguity to a human rather than guessing.

    Returns the number of messages recovered (a plain count — the caller
    logs/exposes it as a metric the same way OutboxWorker.recover_zombies()'s
    own return value already is).
    """
    timeout = (
        timeout_seconds
        if timeout_seconds is not None
        else settings.stale_sending_message_timeout_seconds
    )
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=timeout)

    stale = list(
        db.scalars(
            select(Message)
            .where(Message.status == "sending", Message.updated_at < cutoff)
            .order_by(Message.updated_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
    )
    if not stale:
        return 0

    for message in stale:
        stuck_for = datetime.now(timezone.utc).replace(tzinfo=None) - message.updated_at
        message.status = "failed"
        message.ai_meta = {**(message.ai_meta or {}), "failure_reason": "stale_sending_recovered"}
        logger.warning(
            "Recovered stale sending message %s (business=%s conversation=%s type=%s "
            "stuck_for=%ss) -> failed",
            message.id,
            message.business_id,
            message.conversation_id,
            message.type,
            int(stuck_for.total_seconds()),
        )
        if message.type == "tool_call":
            db.add(
                Escalation(
                    business_id=message.business_id,
                    conversation_id=message.conversation_id,
                    reason="external_failure",
                    status="open",
                )
            )
            logger.error(
                "Stale sending message %s was a tool call (%s) for business %s — escalated "
                "for manual review; an external side effect may have already occurred with "
                "no local record of it",
                message.id,
                (message.ai_meta or {}).get("tool_name"),
                message.business_id,
            )

    db.commit()
    return len(stale)
