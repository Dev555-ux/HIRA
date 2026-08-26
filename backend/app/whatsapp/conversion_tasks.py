"""Outbox task that reports a qualified lead to Meta as a `LeadSubmitted`
conversion event (Sprint 73).

Why a job and not an inline call: `update_lead` runs inside a user request
(PATCH /api/v1/leads/{id}) and inside the AI reply path — neither can afford
to block on a Graph API round-trip, and neither should fail because Meta is
briefly unreachable. Enqueueing inside the caller's own transaction means the
stage change and the intent to report it commit atomically: no event is ever
sent for a stage change that rolled back, and no stage change is lost because
sending failed.

Idempotency is the outbox's, not a new mechanism: the job is enqueued under
`idempotency_key = "ctwa_lead_submitted:{lead_id}"`, which is UNIQUE on
`job_outbox` (see app/jobs/models.py). A lead that moves qualified ->
contacted -> qualified again enqueues once, forever — the second enqueue is a
logged no-op returning None. This matters because Meta explicitly does not
deduplicate Business Messaging conversion events; the sender must.

Registration mirrors app/ai/tasks.py exactly (`ensure_registered()`, called
at import and idempotent) so the worker picks this handler up the same way it
picks up `generate_ai_reply`.

Scope: `LeadSubmitted` only. No Purchase, no Schedule, no backfill of leads
already qualified before this shipped.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.jobs.handlers import PermanentJobError, TransientJobError, is_registered, register_handler
from app.jobs.models import JobOutbox
from app.jobs.queue import enqueue_job
from app.models import Business, Conversation, Lead
from app.whatsapp.conversions import (
    LEAD_SUBMITTED,
    ConversionEventError,
    resolve_dataset_id,
    send_conversion_event,
)
from app.whatsapp.credentials import get_access_token, get_stored_credential

logger = logging.getLogger(__name__)

SEND_LEAD_SUBMITTED_TASK = "send_ctwa_lead_submitted"

QUALIFIED_STAGE = "qualified"

# Returned by `enqueue_lead_submitted` when this lead's conversation did not
# originate from a Click-to-WhatsApp ad. Not an error: most leads are not
# ad-attributed, and there is nothing to report to Meta for them.
NOT_ATTRIBUTABLE = "not attributable to a Click-to-WhatsApp ad"


def find_ctwa_clid(db: Session, business_id: uuid.UUID, customer_id: uuid.UUID) -> str | None:
    """The ad click that opened this customer's conversation, if any.

    A Lead is 1:1 with a Customer (DEC-031) but a Customer can accumulate more
    than one Conversation over time (a closed thread plus a new active one).
    Only one of them can carry a click id in practice — `ctwa_clid` is written
    once, on the first message of an ad-originated thread — so the newest
    non-NULL one is the click that produced this lead.
    """
    return db.scalars(
        select(Conversation.ctwa_clid)
        .where(
            Conversation.business_id == business_id,
            Conversation.customer_id == customer_id,
            Conversation.ctwa_clid.is_not(None),
        )
        .order_by(Conversation.created_at.desc())
    ).first()


def enqueue_lead_submitted(db: Session, lead: Lead) -> str | None:
    """Queue a LeadSubmitted event for `lead`, inside the caller's transaction.

    Returns None when the event was queued (or was already queued earlier,
    which is the same outcome from the caller's point of view), or
    NOT_ATTRIBUTABLE when this lead has no Click-to-WhatsApp click id and
    therefore nothing to report. Never raises, never calls Meta, never
    commits — the caller's own commit is what makes the job real.
    """
    ctwa_clid = find_ctwa_clid(db, lead.business_id, lead.customer_id)
    if not ctwa_clid:
        logger.info(
            "Lead %s qualified but %s; no conversion event queued", lead.id, NOT_ATTRIBUTABLE
        )
        return NOT_ATTRIBUTABLE

    enqueue_job(
        db,
        business_id=lead.business_id,
        task_name=SEND_LEAD_SUBMITTED_TASK,
        payload={"lead_id": str(lead.id)},
        idempotency_key=f"ctwa_lead_submitted:{lead.id}",
    )
    return None


def handle_send_lead_submitted(db: Session, job: JobOutbox) -> None:
    """Send one LeadSubmitted event. Runs in the worker's per-job transaction:
    the dataset id cached below commits atomically with the job being marked
    COMPLETED, so a retry never re-does a successful lookup and a failed job
    never leaves a half-written business row.

    Ordering note: the Graph POST happens before the worker commits, so a
    commit failure after a successful send would retry an already-delivered
    event. The `idempotency_key` prevents a *duplicate lead* producing a
    second job, but not that narrow crash window — the same accepted gap
    `handle_generate_ai_reply` documents for its own external side effects.
    In practice the only row this handler writes is a cached dataset id, so
    the window is one Graph call wide and Meta tolerates a repeat far better
    than a missing event.
    """
    lead = db.get(Lead, uuid.UUID(job.payload["lead_id"]))
    if lead is None or lead.business_id != job.business_id:
        raise PermanentJobError(f"Lead {job.payload['lead_id']} not found for this business")

    ctwa_clid = find_ctwa_clid(db, lead.business_id, lead.customer_id)
    if not ctwa_clid:
        # Only reachable if the conversation was deleted between enqueue and
        # run. Nothing to report and nothing a retry recovers.
        raise PermanentJobError(f"Lead {lead.id} is {NOT_ATTRIBUTABLE}")

    business = db.get(Business, lead.business_id)
    if business is None or not business.whatsapp_business_account_id:
        raise PermanentJobError(
            f"Business {lead.business_id} has no WhatsApp Business Account id to report against"
        )

    credential = get_stored_credential(db, business.id)
    if credential is None:
        raise PermanentJobError(f"Business {business.id} has no stored WhatsApp credentials")
    access_token = get_access_token(credential)

    try:
        if not business.whatsapp_dataset_id:
            business.whatsapp_dataset_id = resolve_dataset_id(
                business.whatsapp_business_account_id, access_token
            )
        send_conversion_event(
            business.whatsapp_dataset_id,
            access_token,
            event_name=LEAD_SUBMITTED,
            whatsapp_business_account_id=business.whatsapp_business_account_id,
            ctwa_clid=ctwa_clid,
            event_time=int(datetime.now(UTC).timestamp()),
        )
    except ConversionEventError as exc:
        if exc.retryable:
            raise TransientJobError(str(exc)) from exc
        raise PermanentJobError(str(exc)) from exc


def ensure_registered() -> None:
    """Register this handler if it isn't already. Idempotent, so it is safe to
    call at import, from scripts/run_worker.py, and from tests that clear the
    registry — same contract as app/ai/tasks.py::ensure_registered."""
    if not is_registered(SEND_LEAD_SUBMITTED_TASK):
        register_handler(SEND_LEAD_SUBMITTED_TASK, handle_send_lead_submitted)


ensure_registered()
