"""PR 4 (ADR-001 / IMP-001) — integration tests for the WhatsApp webhook's
transactional-outbox path.

Verifies the first production workflow migrated onto the outbox: an inbound
WhatsApp message enqueues a `generate_ai_reply` job inside the webhook's DB
transaction (feature-flagged), a worker later claims and dispatches it exactly
once, and duplicate deliveries never double-enqueue. The legacy BackgroundTasks
path is verified to remain unchanged when the flag is off.

Reuses the signature/business/credential helpers established in
tests/test_whatsapp_webhook.py.
"""

import hashlib
import hmac
import json
import uuid

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.ai import tasks as ai_tasks
from app.core.config import settings
from app.db.session import get_db
from app.jobs.models import JobOutbox, JobStatus
from app.main import app
from app.models import Business, Message
from app.webhooks.whatsapp import get_reply_dispatcher
from app.whatsapp.credentials import store_credentials

TEST_APP_SECRET = "test-app-secret"


@pytest.fixture(autouse=True)
def _whatsapp_encryption_key(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())


@pytest.fixture(autouse=True)
def _ensure_handler_registered():
    """The real AI-reply handler must be registered for the worker-execution
    tests; other test modules may have cleared the module-level registry."""
    ai_tasks.ensure_registered()
    yield


def _client(db_session):
    """(client, dispatched). The legacy dispatcher is overridden to record calls
    rather than schedule real generation — so `dispatched` is our probe for
    whether the legacy path ran."""
    dispatched: list[tuple] = []

    def fake_dispatcher():
        def dispatch(background_tasks, conversation_id, message_id, user_text):
            dispatched.append((conversation_id, message_id, user_text))

        return dispatch

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_reply_dispatcher] = fake_dispatcher
    return TestClient(app), dispatched


def _connected_business(db, phone_number_id="PN1", app_secret=TEST_APP_SECRET) -> Business:
    business = Business(name="Clinic A", whatsapp_phone_number_id=phone_number_id)
    db.add(business)
    db.flush()
    store_credentials(db, business.id, access_token="test-token", app_secret=app_secret)
    db.commit()
    return business


def _sign(body: bytes, app_secret: str = TEST_APP_SECRET) -> str:
    return f"sha256={hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()}"


def _payload(phone_number_id: str, wa_message_id: str, from_phone="+15551230000", text="Hi there"):
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [{"wa_id": from_phone, "profile": {"name": "Test User"}}],
                            "messages": [
                                {
                                    "id": wa_message_id,
                                    "from": from_phone,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


def _post(client, phone_number_id, wa_message_id, app_secret=TEST_APP_SECRET, **kw):
    body = json.dumps(_payload(phone_number_id, wa_message_id, **kw)).encode()
    return client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={
            "X-Hub-Signature-256": _sign(body, app_secret),
            "Content-Type": "application/json",
        },
    )


def _jobs(db):
    return db.scalars(select(JobOutbox)).all()


@pytest.fixture
def outbox_on(monkeypatch):
    monkeypatch.setattr(settings, "use_transactional_outbox", True)


@pytest.fixture
def outbox_off(monkeypatch):
    monkeypatch.setattr(settings, "use_transactional_outbox", False)


class TestFeatureFlag:
    def test_flag_on_enqueues_a_job_and_skips_the_legacy_path(self, db_session, outbox_on):
        _connected_business(db_session)
        client, dispatched = _client(db_session)

        resp = _post(client, "PN1", "wamid.enqueue")
        assert resp.status_code == 200

        jobs = _jobs(db_session)
        assert len(jobs) == 1
        job = jobs[0]
        assert job.task_name == ai_tasks.GENERATE_AI_REPLY_TASK
        assert job.status is JobStatus.PENDING
        assert job.idempotency_key == "whatsapp:wamid.enqueue"

        inbound = db_session.scalars(select(Message).where(Message.direction == "inbound")).one()
        assert job.payload["conversation_id"] == str(inbound.conversation_id)
        assert job.payload["message_id"] == str(inbound.id)
        assert job.payload["user_text"] == "Hi there"
        assert job.business_id == inbound.business_id

        # Legacy in-process dispatch must NOT have run.
        assert dispatched == []
        app.dependency_overrides.clear()

    def test_flag_off_uses_legacy_path_and_enqueues_nothing(self, db_session, outbox_off):
        _connected_business(db_session)
        client, dispatched = _client(db_session)

        resp = _post(client, "PN1", "wamid.legacy")
        assert resp.status_code == 200

        assert _jobs(db_session) == []  # no outbox job
        assert len(dispatched) == 1  # legacy generation scheduled instead
        app.dependency_overrides.clear()

    def test_job_and_message_commit_atomically(self, db_session, outbox_on):
        """The enqueue rides the webhook's own transaction: the inbound message
        and its job are both present (a separate connection can see them)."""
        _connected_business(db_session)
        client, _ = _client(db_session)
        _post(client, "PN1", "wamid.atomic")

        engine = db_session.get_bind()
        other = sessionmaker(bind=engine)()
        try:
            assert len(other.scalars(select(JobOutbox)).all()) == 1
            assert (
                len(other.scalars(select(Message).where(Message.direction == "inbound")).all()) == 1
            )
        finally:
            other.close()
        app.dependency_overrides.clear()


class TestDuplicateDelivery:
    def test_duplicate_webhook_delivery_enqueues_one_job(self, db_session, outbox_on):
        _connected_business(db_session)
        client, _ = _client(db_session)

        r1 = _post(client, "PN1", "wamid.dup")
        r2 = _post(client, "PN1", "wamid.dup")  # same wa_message_id again
        assert r1.status_code == 200 and r2.status_code == 200

        inbound = db_session.scalars(select(Message).where(Message.direction == "inbound")).all()
        assert len(inbound) == 1  # message deduped
        assert len(_jobs(db_session)) == 1  # and exactly one job
        app.dependency_overrides.clear()


class TestWorkerExecution:
    def _worker(self, db_session):
        from app.jobs.worker import OutboxWorker

        factory = sessionmaker(bind=db_session.get_bind(), autoflush=False, autocommit=False)
        return OutboxWorker(session_factory=factory, worker_id="test-worker")

    def test_worker_claims_and_runs_the_reply_handler_exactly_once(
        self, db_session, outbox_on, monkeypatch
    ):
        _connected_business(db_session)
        client, _ = _client(db_session)
        _post(client, "PN1", "wamid.run", text="Are you open Saturday?")

        job = db_session.scalars(select(JobOutbox)).one()
        expected_conversation = uuid.UUID(job.payload["conversation_id"])
        expected_message = uuid.UUID(job.payload["message_id"])

        # Stub the deep AI work; we're testing the outbox->handler wiring, not
        # generation internals (covered by the AI test suite). The handler now
        # calls generate_reply_into_session(db, ...) through the worker's own
        # session (Critical audit fix #3) rather than the self-contained
        # generate_and_store_reply, so the stub's signature takes `db` too.
        calls: list[tuple] = []

        def fake_generate(db, conversation_id, message_id, user_text, **kw):
            calls.append((conversation_id, message_id, user_text))
            return []

        monkeypatch.setattr(ai_tasks, "generate_reply_into_session", fake_generate)

        # Release the webhook's transaction so the worker's own session can claim.
        db_session.rollback()

        processed = self._worker(db_session).run_once()
        assert processed == 1
        assert calls == [(expected_conversation, expected_message, "Are you open Saturday?")]

        db_session.expire_all()
        assert db_session.get(JobOutbox, job.id).status is JobStatus.COMPLETED

        # Exactly once: a second cycle finds no due work and never re-runs it.
        assert self._worker(db_session).run_once() == 0
        assert len(calls) == 1
        app.dependency_overrides.clear()

    def test_webhook_returns_without_running_generation_inline(
        self, db_session, outbox_on, monkeypatch
    ):
        """The webhook returns 200 having only enqueued — generation happens
        later, in the worker, not inside the request."""
        _connected_business(db_session)
        client, dispatched = _client(db_session)

        ran_inline: list[str] = []
        monkeypatch.setattr(
            ai_tasks,
            "generate_reply_into_session",
            lambda *a, **k: ran_inline.append("ran"),
        )

        resp = _post(client, "PN1", "wamid.fast")
        assert resp.status_code == 200
        assert ran_inline == []  # not generated during the request
        assert dispatched == []  # nor scheduled via the legacy path
        assert len(_jobs(db_session)) == 1  # only enqueued
        app.dependency_overrides.clear()
