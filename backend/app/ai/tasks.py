"""Outbox task handlers for AI reply generation (Sprint 64 — ADR-001 / IMP-001, PR 4).

The first — and, in PR 4, only — production workflow migrated onto the
transactional outbox: generating the AI reply to an inbound WhatsApp message.

This module is the seam between the worker (which knows nothing about business
logic) and `app.ai.processing.generate_and_store_reply` (which knows nothing
about the outbox). The handler is a thin adapter: it unpacks the job payload and
calls the existing function *unchanged*.

`generate_and_store_reply` deliberately manages its own DB session and swallows
its own errors — an LLM/commit failure is turned into a customer-visible
escalation and the function returns normally (see its module docstring). That is
exactly the fire-and-forget contract the old `BackgroundTasks` path had, so
running it through the worker keeps behaviour identical from the customer's point
of view, while adding durability (the job survives a process restart between the
webhook ack and generation) and idempotency (a redelivered webhook can't enqueue
a second job). Because the function never raises, the worker records the job
COMPLETED after one call — the reply is generated exactly once per delivery.

Registration is idempotent (`ensure_registered`) and runs at import, so simply
importing this module — which `scripts/run_worker.py` does on startup, and the
webhook does transitively — is enough for the worker to discover the handler.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.ai.processing import generate_and_store_reply
from app.jobs.handlers import is_registered, register_handler
from app.jobs.models import JobOutbox

# The canonical task_name for this workflow. The webhook enqueues under it and
# the worker dispatches on it; keeping it a single constant means the two sides
# can never drift.
GENERATE_AI_REPLY_TASK = "generate_ai_reply"


def handle_generate_ai_reply(db: Session, job: JobOutbox) -> None:
    """Adapter: run `generate_and_store_reply` for a claimed outbox job.

    The worker's `db`/`job` are the dispatch contract; the actual work uses the
    self-contained function's own session, exactly as under the legacy
    BackgroundTasks path. UUIDs are stored as strings in the JSONB payload
    (JSON has no UUID type) and parsed back here.
    """
    payload = job.payload
    generate_and_store_reply(
        uuid.UUID(payload["conversation_id"]),
        uuid.UUID(payload["message_id"]),
        payload["user_text"],
    )


def ensure_registered() -> None:
    """Register the AI-reply handler if it isn't already. Idempotent, so it is
    safe to call at import, from `scripts/run_worker.py`, and from tests that
    clear the registry."""
    if not is_registered(GENERATE_AI_REPLY_TASK):
        register_handler(GENERATE_AI_REPLY_TASK, handle_generate_ai_reply)


ensure_registered()
