"""Critical audit fix #3 — tests for the AI-reply job handler's transaction
ownership and replay-safety.

Covers: the handler writes through the worker's own session (no independent
commit), a crash/zombie-recovered/retried replay of the same job is a safe
no-op once the first attempt has actually committed, and multiple workers /
repeated recovery sweeps stay safe. See app/ai/processing.py::
generate_reply_into_session and app/ai/tasks.py::handle_generate_ai_reply for
the implementation this exercises.
"""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.ai import tasks as ai_tasks
from app.ai.llm.base import ToolCall
from app.ai.llm.mock import MockProvider
from app.ai.processing import generate_reply_into_session
from app.ai.tasks import GENERATE_AI_REPLY_TASK, handle_generate_ai_reply
from app.ai.tools import BOOK_APPOINTMENT
from app.calendar.providers.mock import MockCalendarProvider
from app.calendar.service import AppointmentService
from app.core.config import settings
from app.jobs.models import JobOutbox, JobStatus
from app.jobs.worker import OutboxWorker
from app.models import Appointment, Business, Conversation, Customer, ExecutionTrace, Message
from app.whatsapp.credentials import store_credentials
from tests.conftest import TEST_DATABASE_URL


@pytest.fixture(autouse=True)
def _ensure_handler_registered():
    """Other test modules clear the module-level handler registry; the real
    handler must be registered for these tests regardless of run order."""
    ai_tasks.ensure_registered()
    yield


def _stub_whatsapp_transport(monkeypatch, *, wa_message_id="wamid.test"):
    """The handler always calls the real app.services.messaging.send_text
    (there's no way to inject a fake `sender` through the worker/handler
    path — see generate_reply_into_session's default parameter), so a real
    outbound HTTP call must be intercepted at the transport layer or these
    tests would hit the actual Meta Graph API. Patching httpx.Client.post
    directly — not `app.ai.processing.send_text` — because that name is
    bound as a default argument value at import time; reassigning the
    module attribute afterwards doesn't change what already-defined
    functions call.
    """

    def _fake_post(self, url, *, headers=None, json=None, **kwargs):
        return httpx.Response(200, json={"messages": [{"id": wa_message_id}]})

    monkeypatch.setattr(httpx.Client, "post", _fake_post)


def _autonomous_business(db, monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
    biz = Business(name="Auto Clinic", mode="autonomous", whatsapp_phone_number_id="PN1")
    db.add(biz)
    db.flush()
    store_credentials(db, biz.id, access_token="test-token", app_secret="test-secret")
    customer = Customer(business_id=biz.id, wa_phone="+15550001111")
    db.add(customer)
    db.flush()
    conversation = Conversation(business_id=biz.id, customer_id=customer.id)
    db.add(conversation)
    db.flush()
    trigger = Message(
        conversation_id=conversation.id,
        business_id=biz.id,
        direction="inbound",
        body="Are you open Saturday?",
        type="text",
        status="received",
    )
    db.add(trigger)
    db.flush()
    db.commit()
    return biz, conversation, trigger


def _make_reply_job(db, business, conversation, trigger, *, user_text="Are you open Saturday?"):
    job = JobOutbox(
        business_id=business.id,
        task_name=GENERATE_AI_REPLY_TASK,
        payload={
            "conversation_id": str(conversation.id),
            "message_id": str(trigger.id),
            "user_text": user_text,
        },
    )
    db.add(job)
    db.flush()
    db.commit()
    return job


def _worker(db_session, *, worker_id="w1", **kwargs):
    factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
    return OutboxWorker(session_factory=factory, worker_id=worker_id, **kwargs)


def _fresh_session():
    """A brand-new session against the same test database, standing in for a
    worker process's own per-job session in tests that need to hold one open
    independently of db_session's own transaction/connection."""
    return sessionmaker(bind=create_engine(TEST_DATABASE_URL), autoflush=False, autocommit=False)()


# --- 1. Normal reply generation ---------------------------------------------


def test_normal_reply_generation_commits_reply_and_job_together(db_session, monkeypatch):
    biz, conversation, trigger = _autonomous_business(db_session, monkeypatch)
    job = _make_reply_job(db_session, biz, conversation, trigger)
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="We are open 9-5 on Saturday."),
    )
    _stub_whatsapp_transport(monkeypatch)

    processed = _worker(db_session).run_once()

    assert processed == 1
    db_session.expire_all()
    assert db_session.get(JobOutbox, job.id).status is JobStatus.COMPLETED
    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1
    assert outbound[0].status == "sent"
    trace = db_session.scalars(select(ExecutionTrace)).one()
    assert trace.trigger_message_id == trigger.id


# --- 2. Crash before job completion / 10. Transaction rollback -------------


def test_handler_writes_are_not_visible_until_the_worker_commits(db_session, monkeypatch):
    """Simulates a crash between the handler's writes and the worker's own
    commit: nothing the handler wrote is visible from another connection
    until *something* commits — proving there is no independent commit
    inside the handler anymore (Part B)."""
    biz, conversation, trigger = _autonomous_business(db_session, monkeypatch)
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="We are open 9-5 on Saturday."),
    )
    _stub_whatsapp_transport(monkeypatch)

    crashing_session = _fresh_session()
    try:
        job = JobOutbox(
            business_id=biz.id,
            task_name=GENERATE_AI_REPLY_TASK,
            payload={
                "conversation_id": str(conversation.id),
                "message_id": str(trigger.id),
                "user_text": "Are you open Saturday?",
            },
        )
        crashing_session.add(job)
        crashing_session.flush()

        handle_generate_ai_reply(crashing_session, job)
        # "Crash" here: the process dies before committing or closing —
        # simulated by simply never calling commit() and observing from a
        # completely separate connection in the meantime.
        assert (
            db_session.scalars(select(Message).where(Message.direction == "outbound")).all() == []
        )
        assert db_session.scalars(select(ExecutionTrace)).all() == []
        assert db_session.scalars(select(JobOutbox)).all() == []
    finally:
        crashing_session.rollback()  # what actually happens when the connection drops
        crashing_session.close()

    # After the "crash", nothing exists anywhere — confirming rollback (not a
    # partial/silent commit) is what a real crash leaves behind.
    assert db_session.scalars(select(Message).where(Message.direction == "outbound")).all() == []
    assert db_session.scalars(select(ExecutionTrace)).all() == []


# --- 3. Zombie recovery / 4. Replay -----------------------------------------


def test_zombie_recovery_returns_a_stuck_job_to_pending_and_it_gets_replayed(
    db_session, monkeypatch
):
    biz, conversation, trigger = _autonomous_business(db_session, monkeypatch)
    job = _make_reply_job(db_session, biz, conversation, trigger)
    # Simulate a worker that claimed the job and then died: PROCESSING, with
    # locked_at far enough in the past to be past the zombie timeout.
    job.status = JobStatus.PROCESSING
    job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=10_000)
    job.locked_by = "dead-worker"
    db_session.commit()

    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="We are open 9-5 on Saturday."),
    )
    _stub_whatsapp_transport(monkeypatch)

    worker = _worker(db_session, zombie_timeout_seconds=300)
    recovered = worker.recover_zombies()
    assert recovered == 1
    db_session.expire_all()
    assert db_session.get(JobOutbox, job.id).status is JobStatus.PENDING

    processed = worker.run_once()
    assert processed == 1
    db_session.expire_all()
    assert db_session.get(JobOutbox, job.id).status is JobStatus.COMPLETED
    assert (
        len(db_session.scalars(select(Message).where(Message.direction == "outbound")).all()) == 1
    )


# --- 5/6/7. Duplicate reply / tool-execution / appointment prevention ------


def test_replaying_a_committed_job_produces_no_duplicate_reply(db_session, monkeypatch):
    """The core Critical-#3 guarantee: once a turn has actually committed
    (trace + messages), re-running the exact same job for the same
    trigger_message_id — as a zombie-recovery replay or a retry would —
    writes nothing new."""
    biz, conversation, trigger = _autonomous_business(db_session, monkeypatch)
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="We are open 9-5 on Saturday."),
    )
    _stub_whatsapp_transport(monkeypatch)

    job = _make_reply_job(db_session, biz, conversation, trigger)
    assert _worker(db_session).run_once() == 1
    db_session.expire_all()
    first_outbound = db_session.scalars(
        select(Message).where(Message.direction == "outbound")
    ).all()
    assert len(first_outbound) == 1
    first_trace = db_session.scalars(select(ExecutionTrace)).one()

    # Replay: put the SAME job back to PENDING (what recover_zombies() does)
    # and process it again.
    job.status = JobStatus.PENDING
    job.locked_at = None
    job.locked_by = None
    db_session.commit()

    assert _worker(db_session).run_once() == 1  # the job still "processes" (and completes)...
    db_session.expire_all()
    # ...but nothing new was written.
    outbound_after_replay = db_session.scalars(
        select(Message).where(Message.direction == "outbound")
    ).all()
    assert len(outbound_after_replay) == 1
    assert outbound_after_replay[0].id == first_outbound[0].id
    traces = db_session.scalars(select(ExecutionTrace)).all()
    assert len(traces) == 1
    assert traces[0].id == first_trace.id
    assert db_session.get(JobOutbox, job.id).status is JobStatus.COMPLETED


def test_replaying_a_committed_booking_does_not_book_twice(db_session, monkeypatch):
    """Same guarantee, for a turn that executed a real (non-governed) tool —
    the audit's explicit "no duplicate booking" scenario."""
    biz, conversation, trigger = _autonomous_business(db_session, monkeypatch)
    booking_call = ToolCall(
        id="1",
        name=BOOK_APPOINTMENT,
        arguments={
            "starts_at": "2026-08-10T14:00:00",
            "ends_at": "2026-08-10T14:30:00",
            "summary": "Cleaning",
        },
    )
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="", fixed_tool_calls=[booking_call]),
    )
    monkeypatch.setattr(
        "app.ai.tools.get_appointment_service",
        lambda db, business_id: AppointmentService(
            db, business_id, MockCalendarProvider(), calendar_id="primary"
        ),
    )
    _stub_whatsapp_transport(monkeypatch)

    job = _make_reply_job(
        db_session, biz, conversation, trigger, user_text="book me tuesday at 2pm"
    )
    assert _worker(db_session).run_once() == 1
    db_session.expire_all()
    assert len(db_session.scalars(select(Appointment)).all()) == 1

    # Zombie-recovery-style replay.
    job.status = JobStatus.PENDING
    job.locked_at = None
    job.locked_by = None
    db_session.commit()
    assert _worker(db_session).run_once() == 1

    db_session.expire_all()
    appointments = db_session.scalars(select(Appointment)).all()
    assert len(appointments) == 1  # not booked twice
    assert len(db_session.scalars(select(ExecutionTrace)).all()) == 1


# --- 8. Multiple worker recovery --------------------------------------------


def test_two_worker_instances_never_both_process_the_same_recovered_job(db_session, monkeypatch):
    biz, conversation, trigger = _autonomous_business(db_session, monkeypatch)
    job = _make_reply_job(db_session, biz, conversation, trigger)
    job.status = JobStatus.PROCESSING
    job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=10_000)
    job.locked_by = "dead-worker"
    db_session.commit()

    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="We are open 9-5 on Saturday."),
    )
    _stub_whatsapp_transport(monkeypatch)

    worker_a = _worker(db_session, worker_id="worker-a", zombie_timeout_seconds=300)
    worker_b = _worker(db_session, worker_id="worker-b", zombie_timeout_seconds=300)

    # Either worker's sweep may be the one that actually flips it back to
    # PENDING first; both are safe to call.
    worker_a.recover_zombies()
    worker_b.recover_zombies()

    processed_a = worker_a.run_once()
    processed_b = worker_b.run_once()
    # FOR UPDATE SKIP LOCKED guarantees only one claims it; the other finds
    # nothing due (already COMPLETED, or in a true race, already claimed).
    assert processed_a + processed_b == 1

    db_session.expire_all()
    assert db_session.get(JobOutbox, job.id).status is JobStatus.COMPLETED
    assert (
        len(db_session.scalars(select(Message).where(Message.direction == "outbound")).all()) == 1
    )


# --- 9. Repeated zombie recovery ---------------------------------------------


def test_repeated_zombie_recovery_sweeps_are_safe_and_idempotent(db_session, monkeypatch):
    biz, conversation, trigger = _autonomous_business(db_session, monkeypatch)
    job = _make_reply_job(db_session, biz, conversation, trigger)
    job.status = JobStatus.PROCESSING
    job.locked_at = datetime.now(timezone.utc) - timedelta(seconds=10_000)
    job.locked_by = "dead-worker"
    db_session.commit()

    worker = _worker(db_session, zombie_timeout_seconds=300)
    assert worker.recover_zombies() == 1
    # Repeated sweeps before anything reclaims it: harmless, nothing left to
    # recover (already PENDING, not PROCESSING, so it no longer matches).
    assert worker.recover_zombies() == 0
    assert worker.recover_zombies() == 0

    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="We are open 9-5 on Saturday."),
    )
    _stub_whatsapp_transport(monkeypatch)
    assert worker.run_once() == 1

    db_session.expire_all()
    assert db_session.get(JobOutbox, job.id).status is JobStatus.COMPLETED
    # A sweep after completion finds nothing (status is COMPLETED, not
    # PROCESSING) — repeated recovery is safe even long after the fact.
    assert worker.recover_zombies() == 0


# --- Idempotency check itself, at the generate_reply_into_session layer ----


def test_generate_reply_into_session_is_a_no_op_for_an_already_recorded_trigger(
    db_session, monkeypatch
):
    biz, conversation, trigger = _autonomous_business(db_session, monkeypatch)
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="We are open 9-5 on Saturday."),
    )

    on_commit_failures_1 = generate_reply_into_session(
        db_session,
        conversation.id,
        trigger.id,
        "Are you open Saturday?",
        sender=lambda *a, **kw: "wamid.1",
    )
    db_session.commit()
    assert on_commit_failures_1 == []
    assert (
        len(db_session.scalars(select(Message).where(Message.direction == "outbound")).all()) == 1
    )

    calls = {"n": 0}

    def _spy_provider(name=None):
        calls["n"] += 1
        return MockProvider(fixed_reply="This should never be used.")

    monkeypatch.setattr("app.ai.orchestrator.get_llm_provider", _spy_provider)

    on_commit_failures_2 = generate_reply_into_session(
        db_session,
        conversation.id,
        trigger.id,
        "Are you open Saturday?",
        sender=lambda *a, **kw: "wamid.2",
    )
    db_session.commit()

    assert on_commit_failures_2 == []
    assert calls["n"] == 0  # the LLM was never even called on the replay
    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 1  # still just the one from the first call


def test_generate_reply_into_session_treats_none_trigger_as_always_fresh(db_session, monkeypatch):
    """None is the legitimate "no specific trigger" value several existing
    callers use — it must never be treated as a duplicate of itself."""
    biz, conversation, trigger = _autonomous_business(db_session, monkeypatch)
    monkeypatch.setattr(
        "app.ai.orchestrator.get_llm_provider",
        lambda name=None: MockProvider(fixed_reply="We are open 9-5 on Saturday."),
    )

    generate_reply_into_session(
        db_session, conversation.id, None, "are you open?", sender=lambda *a, **kw: "wamid.1"
    )
    db_session.commit()
    generate_reply_into_session(
        db_session, conversation.id, None, "are you open?", sender=lambda *a, **kw: "wamid.2"
    )
    db_session.commit()

    outbound = db_session.scalars(select(Message).where(Message.direction == "outbound")).all()
    assert len(outbound) == 2  # both calls produced a real reply
