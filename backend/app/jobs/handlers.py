"""Task handler registry for the outbox worker (Sprint 64 — ADR-001 / IMP-001, PR 3).

The worker (`app/jobs/worker.py`) is deliberately ignorant of business logic: it
claims jobs, dispatches them, and records outcomes. *What* a job actually does
lives in a **handler** registered here against its `task_name`. This split is
the whole point — the worker never grows a switch statement over task names, and
new background work is added by registering a handler, never by touching the
worker.

A handler is any callable ``(db: Session, job: JobOutbox) -> None``:

    from app.jobs.handlers import register

    @register("generate_ai_reply")
    def _generate_ai_reply(db: Session, job: JobOutbox) -> None:
        # do the work using job.business_id / job.payload; write via `db`.
        # `db` is the worker's per-job transaction: anything written here
        # commits atomically with the job being marked COMPLETED.

Failure signalling (see worker.py for how each is recorded):

* return normally         -> COMPLETED
* raise TransientJobError  -> retried with backoff (until max_attempts, then DEAD_LETTER)
* raise PermanentJobError  -> FAILED immediately, never retried
* raise anything else      -> treated as transient (retried), because an
                              unexpected exception is more often a blip than a
                              permanent contract violation

Handlers must treat `db` as the *only* transaction: they must not commit or roll
it back themselves — the worker owns the transaction boundary so that business
writes and the job's terminal status are one atomic unit.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.jobs.models import JobOutbox

logger = logging.getLogger(__name__)

# A handler runs a claimed job inside the worker's per-job transaction.
JobHandler = Callable[[Session, JobOutbox], None]


class JobError(Exception):
    """Base class for the two failure signals a handler can raise."""


class TransientJobError(JobError):
    """A retryable failure (timeout, upstream 5xx, transient lock). The worker
    schedules a backed-off retry until `max_attempts` is reached."""


class PermanentJobError(JobError):
    """A non-retryable failure (malformed payload, business rule permanently
    violated). The worker marks the job FAILED without retrying."""


# task_name -> handler. Module-level singleton: handlers register themselves at
# import time, mirroring how the app wires other global registries.
_REGISTRY: dict[str, JobHandler] = {}


def register(task_name: str) -> Callable[[JobHandler], JobHandler]:
    """Decorator registering `fn` as the handler for `task_name`.

    Raises ValueError on a blank name or a duplicate registration — a duplicate
    almost always means two modules silently claimed the same task, which we
    want to surface loudly at import time rather than let one win at random.
    """

    def decorator(fn: JobHandler) -> JobHandler:
        register_handler(task_name, fn)
        return fn

    return decorator


def register_handler(task_name: str, handler: JobHandler) -> None:
    """Imperative form of `register`, for wiring handlers without a decorator."""
    if not task_name or not task_name.strip():
        raise ValueError("task_name must be a non-empty string")
    task_name = task_name.strip()
    if task_name in _REGISTRY:
        raise ValueError(f"A handler is already registered for task {task_name!r}")
    _REGISTRY[task_name] = handler
    logger.info("Registered outbox handler for task=%s", task_name)


def get_handler(task_name: str) -> JobHandler | None:
    """Return the handler for `task_name`, or None if none is registered.

    Returning None (rather than raising) is intentional: an unknown task must
    never crash the worker — it records the miss and moves on (see worker.py).
    """
    return _REGISTRY.get(task_name)


def is_registered(task_name: str) -> bool:
    return task_name in _REGISTRY


def registered_tasks() -> tuple[str, ...]:
    """Snapshot of registered task names (sorted, for stable logging/tests)."""
    return tuple(sorted(_REGISTRY))


def unregister(task_name: str) -> None:
    """Remove a handler if present. Primarily for tests that register a handler
    and need to leave the module-level registry clean afterwards."""
    _REGISTRY.pop(task_name, None)


def clear_registry() -> None:
    """Drop all registrations. Test-only helper — never call in production."""
    _REGISTRY.clear()
