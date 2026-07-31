"""Background job engine package (Sprint 64 - Transactional Outbox)."""

from app.jobs.handlers import (
    JobError,
    PermanentJobError,
    TransientJobError,
    get_handler,
    register,
    register_handler,
)
from app.jobs.models import JobOutbox, JobStatus
from app.jobs.queue import OutboxService, OutboxValidationError, enqueue_job
from app.jobs.worker import OutboxWorker

__all__ = [
    "JobError",
    "JobOutbox",
    "JobStatus",
    "OutboxService",
    "OutboxValidationError",
    "OutboxWorker",
    "PermanentJobError",
    "TransientJobError",
    "enqueue_job",
    "get_handler",
    "register",
    "register_handler",
]
