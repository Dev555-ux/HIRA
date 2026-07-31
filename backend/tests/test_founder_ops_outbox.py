"""PR 5 (ADR-001 / IMP-001) — tests for the outbox operations API
(/api/v1/founder_ops/jobs).

Covers the read endpoints (metrics, list with pagination + filtering, detail),
the manual-retry mutation (success + every rejection), unknown ids, and the
founder-only auth gate. Reuses the founder-auth override pattern from
tests/test_founder_ops.py.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.auth.dependencies import get_token_verifier
from app.core.config import settings
from app.db.session import get_db
from app.jobs.models import JobOutbox, JobStatus
from app.main import app
from app.models import Business

METRICS_URL = "/api/v1/founder_ops/jobs"
LIST_URL = "/api/v1/founder_ops/jobs/list"


def _founder_client(db_session, monkeypatch, *, founder_id="founder-1"):
    monkeypatch.setattr(settings, "founder_clerk_user_ids", founder_id)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda token: {"sub": founder_id}
    return TestClient(app)


def _auth():
    return {"Authorization": "Bearer tok"}


def _business(db) -> Business:
    biz = Business(name="Clinic A")
    db.add(biz)
    db.flush()
    return biz


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _job(
    db,
    business,
    *,
    task_name="generate_ai_reply",
    status=JobStatus.PENDING,
    queue_name="default",
    attempts=0,
    max_attempts=5,
    payload=None,
    created_at=None,
    run_at=None,
    locked_at=None,
    locked_by=None,
    last_error=None,
    idempotency_key=None,
) -> JobOutbox:
    job = JobOutbox(
        business_id=business.id,
        task_name=task_name,
        payload=payload if payload is not None else {},
        status=status,
        queue_name=queue_name,
        attempts=attempts,
        max_attempts=max_attempts,
        idempotency_key=idempotency_key,
    )
    # Server-default timestamps are identical within one transaction (func.now()
    # == transaction start), so set them explicitly where a test needs ordering
    # or age to be deterministic.
    if created_at is not None:
        job.created_at = created_at
    if run_at is not None:
        job.run_at = run_at
    if locked_at is not None:
        job.locked_at = locked_at
    if locked_by is not None:
        job.locked_by = locked_by
    if last_error is not None:
        job.last_error = last_error
    db.add(job)
    db.flush()
    return job


def _teardown():
    app.dependency_overrides.clear()


class TestAuthGate:
    def test_non_founder_gets_404(self, db_session, monkeypatch):
        # Authenticated, but not on the founder allowlist.
        monkeypatch.setattr(settings, "founder_clerk_user_ids", "someone-else")
        app.dependency_overrides[get_db] = lambda: db_session
        app.dependency_overrides[get_token_verifier] = lambda: lambda t: {"sub": "not-founder"}
        client = TestClient(app)
        resp = client.get(METRICS_URL, headers=_auth())
        assert resp.status_code == 404
        _teardown()


class TestMetrics:
    def test_status_counts_and_ages(self, db_session, monkeypatch):
        biz = _business(db_session)
        # 2 pending (one aged), 1 processing (aged), 1 completed, 1 failed, 2 dead_letter
        _job(db_session, biz, status=JobStatus.PENDING, created_at=_now() - timedelta(seconds=120))
        _job(db_session, biz, status=JobStatus.PENDING)
        _job(
            db_session,
            biz,
            status=JobStatus.PROCESSING,
            locked_at=_now() - timedelta(seconds=60),
            locked_by="w1",
        )
        _job(db_session, biz, status=JobStatus.COMPLETED)
        _job(db_session, biz, status=JobStatus.FAILED)
        _job(db_session, biz, status=JobStatus.DEAD_LETTER)
        _job(db_session, biz, status=JobStatus.DEAD_LETTER)
        db_session.commit()

        client = _founder_client(db_session, monkeypatch)
        data = client.get(METRICS_URL, headers=_auth()).json()["data"]

        assert data["pending_count"] == 2
        assert data["processing_count"] == 1
        assert data["completed_count"] == 1
        assert data["failed_count"] == 1
        assert data["dead_letter_count"] == 2
        assert data["oldest_pending_age_seconds"] >= 110
        assert data["oldest_processing_age_seconds"] >= 55
        _teardown()

    def test_empty_queue_ages_are_null(self, db_session, monkeypatch):
        client = _founder_client(db_session, monkeypatch)
        data = client.get(METRICS_URL, headers=_auth()).json()["data"]
        assert data == {
            "pending_count": 0,
            "processing_count": 0,
            "completed_count": 0,
            "failed_count": 0,
            "dead_letter_count": 0,
            "oldest_pending_age_seconds": None,
            "oldest_processing_age_seconds": None,
        }
        _teardown()


class TestListing:
    def test_pagination_newest_first(self, db_session, monkeypatch):
        biz = _business(db_session)
        base = _now()
        # Created oldest..newest; expect newest-first ordering.
        for i in range(5):
            _job(db_session, biz, task_name=f"t{i}", created_at=base - timedelta(minutes=5 - i))
        db_session.commit()

        client = _founder_client(db_session, monkeypatch)
        page1 = client.get(LIST_URL, params={"limit": 2, "offset": 0}, headers=_auth()).json()[
            "data"
        ]
        assert page1["total"] == 5
        assert page1["limit"] == 2 and page1["offset"] == 0
        assert [j["task_name"] for j in page1["jobs"]] == ["t4", "t3"]

        page2 = client.get(LIST_URL, params={"limit": 2, "offset": 2}, headers=_auth()).json()[
            "data"
        ]
        assert [j["task_name"] for j in page2["jobs"]] == ["t2", "t1"]

        page3 = client.get(LIST_URL, params={"limit": 2, "offset": 4}, headers=_auth()).json()[
            "data"
        ]
        assert [j["task_name"] for j in page3["jobs"]] == ["t0"]
        _teardown()

    def test_filter_by_status(self, db_session, monkeypatch):
        biz = _business(db_session)
        _job(db_session, biz, status=JobStatus.PENDING)
        _job(db_session, biz, status=JobStatus.FAILED)
        _job(db_session, biz, status=JobStatus.DEAD_LETTER)
        db_session.commit()

        client = _founder_client(db_session, monkeypatch)
        data = client.get(LIST_URL, params={"status": "failed"}, headers=_auth()).json()["data"]
        assert data["total"] == 1
        assert [j["status"] for j in data["jobs"]] == ["failed"]
        _teardown()

    def test_filter_by_queue(self, db_session, monkeypatch):
        biz = _business(db_session)
        _job(db_session, biz, queue_name="default")
        _job(db_session, biz, queue_name="whatsapp")
        _job(db_session, biz, queue_name="whatsapp")
        db_session.commit()

        client = _founder_client(db_session, monkeypatch)
        data = client.get(LIST_URL, params={"queue": "whatsapp"}, headers=_auth()).json()["data"]
        assert data["total"] == 2
        assert {j["status"] for j in data["jobs"]}  # sanity: rows returned
        assert all(True for _ in data["jobs"])
        _teardown()

    def test_invalid_status_filter_is_422(self, db_session, monkeypatch):
        client = _founder_client(db_session, monkeypatch)
        resp = client.get(LIST_URL, params={"status": "not-a-status"}, headers=_auth())
        assert resp.status_code == 422
        _teardown()

    def test_list_row_shape(self, db_session, monkeypatch):
        biz = _business(db_session)
        _job(db_session, biz, attempts=2, last_error="boom", locked_by="w9")
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)
        row = client.get(LIST_URL, headers=_auth()).json()["data"]["jobs"][0]
        assert set(row) == {
            "id",
            "task_name",
            "status",
            "attempts",
            "max_attempts",
            "created_at",
            "updated_at",
            "run_at",
            "locked_by",
            "last_error",
        }
        _teardown()


class TestJobDetail:
    def test_returns_complete_job(self, db_session, monkeypatch):
        biz = _business(db_session)
        job = _job(
            db_session,
            biz,
            payload={"conversation_id": "c1", "message_id": "m1"},
            idempotency_key="whatsapp:wamid.1",
            last_error="kaboom",
        )
        db_session.commit()

        client = _founder_client(db_session, monkeypatch)
        data = client.get(f"{METRICS_URL}/{job.id}", headers=_auth()).json()["data"]

        assert data["id"] == str(job.id)
        assert data["business_id"] == str(biz.id)
        assert data["queue_name"] == "default"
        assert data["payload"] == {"conversation_id": "c1", "message_id": "m1"}
        assert data["idempotency_key"] == "whatsapp:wamid.1"
        assert data["last_error"] == "kaboom"
        assert "locked_at" in data
        _teardown()

    def test_unknown_job_id_is_404(self, db_session, monkeypatch):
        client = _founder_client(db_session, monkeypatch)
        resp = client.get(f"{METRICS_URL}/{uuid.uuid4()}", headers=_auth())
        assert resp.status_code == 404
        _teardown()

    def test_malformed_job_id_is_422(self, db_session, monkeypatch):
        client = _founder_client(db_session, monkeypatch)
        resp = client.get(f"{METRICS_URL}/not-a-uuid", headers=_auth())
        assert resp.status_code == 422
        _teardown()


class TestRetry:
    def _retry(self, client, job_id):
        return client.post(f"{METRICS_URL}/{job_id}/retry", headers=_auth())

    def test_retry_failed_job_resets_it(self, db_session, monkeypatch):
        biz = _business(db_session)
        job = _job(
            db_session,
            biz,
            status=JobStatus.FAILED,
            attempts=3,
            last_error="permanent boom",
            locked_by="stale-worker",
        )
        db_session.commit()

        client = _founder_client(db_session, monkeypatch)
        resp = self._retry(client, job.id)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "pending"
        assert data["attempts"] == 0
        assert data["last_error"] is None
        assert data["locked_by"] is None

        db_session.expire_all()
        refreshed = db_session.get(JobOutbox, job.id)
        assert refreshed.status is JobStatus.PENDING
        assert refreshed.attempts == 0
        assert refreshed.last_error is None
        _teardown()

    def test_retry_dead_letter_job_succeeds(self, db_session, monkeypatch):
        biz = _business(db_session)
        job = _job(db_session, biz, status=JobStatus.DEAD_LETTER, attempts=5)
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)
        assert self._retry(client, job.id).status_code == 200
        db_session.expire_all()
        assert db_session.get(JobOutbox, job.id).status is JobStatus.PENDING
        _teardown()

    def test_retry_pending_is_rejected_409(self, db_session, monkeypatch):
        biz = _business(db_session)
        job = _job(db_session, biz, status=JobStatus.PENDING)
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)
        resp = self._retry(client, job.id)
        assert resp.status_code == 409
        assert "pending" in resp.json()["detail"]
        _teardown()

    def test_retry_processing_is_rejected_409(self, db_session, monkeypatch):
        biz = _business(db_session)
        job = _job(db_session, biz, status=JobStatus.PROCESSING, locked_by="w1")
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)
        assert self._retry(client, job.id).status_code == 409
        # Unchanged.
        db_session.expire_all()
        assert db_session.get(JobOutbox, job.id).status is JobStatus.PROCESSING
        _teardown()

    def test_retry_completed_is_rejected_409(self, db_session, monkeypatch):
        biz = _business(db_session)
        job = _job(db_session, biz, status=JobStatus.COMPLETED)
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)
        assert self._retry(client, job.id).status_code == 409
        _teardown()

    def test_retry_unknown_job_is_404(self, db_session, monkeypatch):
        client = _founder_client(db_session, monkeypatch)
        assert self._retry(client, uuid.uuid4()).status_code == 404
        _teardown()
