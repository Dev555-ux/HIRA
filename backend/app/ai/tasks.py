"""Outbox task handlers for AI reply generation (Sprint 64 — ADR-001 / IMP-001, PR 4).

The first — and, in PR 4, only — production workflow migrated onto the
transactional outbox: generating the AI reply to an inbound WhatsApp message.

This module is the seam between the worker (which knows nothing about business
logic) and `app.ai.processing` (which knows nothing about the outbox). The
handler is a thin adapter: it unpacks the job payload and calls
`generate_reply_into_session`, writing through the *worker's own* `db` (Critical
audit fix #3) — not `generate_and_store_reply`, which opens an independent
session of its own and would defeat the point of running this through the
outbox worker at all.

Why this matters (the bug this fix closes): the worker's whole safety model is
"a job's business writes and its COMPLETED status commit together, atomically,
in one transaction the worker owns" (see app/jobs/worker.py's module docstring)
— that's what makes replaying a job after a crash (the zombie sweep) safe. A
handler that committed its own, separate transaction broke that: a crash between
that inner commit and the worker's own left the job PROCESSING, the zombie sweep
returned it to PENDING, and replaying it ran the *entire* turn again from
scratch — a second AI reply, and potentially a second tool execution (a second
appointment, a second CRM update), even though the first attempt had already
fully succeeded and committed.

Two things now make replay (whether via the zombie sweep or an ordinary
transient-failure retry) safe:

1. `db` here *is* the worker's per-job session — nothing this handler triggers
   commits until `app/jobs/worker.py::OutboxWorker._process_job` does, right
   before marking the job COMPLETED. No nested commits, no partial commits.
2. `generate_reply_into_session` is idempotent on `job.payload["message_id"]`
   (the triggering inbound Message's id): if an ExecutionTrace already exists
   for it, a prior attempt already ran this exact turn to completion and
   committed, so this call is a no-op — see that function's own docstring.

Registration is idempotent (`ensure_registered`) and runs at import, so simply
importing this module — which `scripts/run_worker.py` does on startup, and the
webhook does transitively — is enough for the worker to discover the handler.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.ai.processing import generate_reply_into_session
from app.jobs.handlers import is_registered, register_handler
from app.jobs.models import JobOutbox

logger = logging.getLogger(__name__)

# The canonical task_name for this workflow. The webhook enqueues under it and
# the worker dispatches on it; keeping it a single constant means the two sides
# can never drift.
GENERATE_AI_REPLY_TASK = "generate_ai_reply"


def handle_generate_ai_reply(db: Session, job: JobOutbox) -> None:
    """Adapter: run one turn's worth of `generate_reply_into_session` through
    this claimed job's own transaction. UUIDs are stored as strings in the
    JSONB payload (JSON has no UUID type) and parsed back here.

    The returned on_commit_failure compensations (Section A4 — e.g. delete a
    calendar event that was already created externally before a failed local
    commit rolled back the Appointment row that would have referenced it) are
    a known, accepted gap in this path: this handler doesn't commit, the
    worker does (after this function returns), so there is no local hook left
    to run them against *this specific* commit if it fails — the worker's own
    generic per-job failure handling (rollback, then a backed-off retry) still
    applies uniformly, same as for any other handler's commit failure, it just
    won't clean up an already-created external event on that path. Logged
    loudly rather than silently dropped, so this gap stays visible instead of
    quietly happening in production with no trace.
    """
    payload = job.payload
    on_commit_failures = generate_reply_into_session(
        db,
        uuid.UUID(payload["conversation_id"]),
        uuid.UUID(payload["message_id"]),
        payload["user_text"],
    )
    if on_commit_failures:
        logger.info(
            "generate_ai_reply job=%s has %d on_commit_failure compensation(s) pending on the "
            "worker's own commit; not independently actionable from this handler — see this "
            "function's own docstring",
            job.id,
            len(on_commit_failures),
        )


def ensure_registered() -> None:
    """Register the AI-reply handler if it isn't already. Idempotent, so it is
    safe to call at import, from `scripts/run_worker.py`, and from tests that
    clear the registry."""
    if not is_registered(GENERATE_AI_REPLY_TASK):
        register_handler(GENERATE_AI_REPLY_TASK, handle_generate_ai_reply)


ensure_registered()
