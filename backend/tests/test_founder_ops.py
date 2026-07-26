"""Tests for the Founder Operations Dashboard API (/api/v1/founder) —
Sprint 73. Covers the founder-only auth gate (the one deliberately
cross-tenant hole in an otherwise tenant-scoped codebase) and the
correctness of every aggregate the dashboard shows."""

import uuid
from datetime import datetime, timedelta, timezone

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app.auth.dependencies import get_token_verifier
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Business, Conversation, Customer, ExecutionTrace, KbEntry, Message
from app.whatsapp.credentials import store_credentials


def _client(db_session, *, claims_for_token):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_token_verifier] = lambda: lambda token: claims_for_token(token)
    return TestClient(app)


def _auth(token="tok"):
    return {"Authorization": f"Bearer {token}"}


def _founder_client(db_session, monkeypatch, *, founder_id="founder-1"):
    monkeypatch.setattr(settings, "founder_clerk_user_ids", founder_id)
    return _client(db_session, claims_for_token=lambda t: {"sub": founder_id})


def _business(db, name, **overrides) -> Business:
    biz = Business(name=name, **overrides)
    db.add(biz)
    db.flush()
    return biz


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _conversation(db, business) -> Conversation:
    customer = Customer(
        business_id=business.id, wa_phone=f"+1555{business.id.int % 10_000_000:07d}"
    )
    db.add(customer)
    db.flush()
    conversation = Conversation(business_id=business.id, customer_id=customer.id, status="active")
    db.add(conversation)
    db.flush()
    return conversation


def _message(db, conversation, business, *, direction, created_at, msg_status=None):
    db.add(
        Message(
            conversation_id=conversation.id,
            business_id=business.id,
            direction=direction,
            body="hi",
            status=msg_status or ("sent" if direction == "outbound" else "received"),
            created_at=created_at,
        )
    )
    db.flush()


def _result_message(db, conversation, business, *, status="sent", body="ok"):
    message = Message(
        conversation_id=conversation.id,
        business_id=business.id,
        direction="outbound",
        body=body,
        status=status,
    )
    db.add(message)
    db.flush()
    return message


def _trace(
    db,
    business,
    conversation,
    *,
    category="action",
    steps=None,
    clarification_hint=None,
    proposed_tool_calls=None,
    result_messages=(),
    duration_ms=100,
    trigger_message_id=None,
):
    trace = ExecutionTrace(
        business_id=business.id,
        conversation_id=conversation.id,
        trigger_message_id=trigger_message_id,
        category=category,
        plan={"category": category, "steps": steps or [], "clarification_hint": clarification_hint},
        proposed_tool_calls=proposed_tool_calls or [],
        result_message_ids=[str(m.id) for m in result_messages],
        duration_ms=duration_ms,
    )
    db.add(trace)
    db.flush()
    return trace


class TestFounderAuthGate:
    def test_requires_authentication(self, db_session):
        _business(db_session, "A")
        db_session.commit()
        app.dependency_overrides[get_db] = lambda: db_session
        client = TestClient(app)

        resp = client.get("/api/v1/founder/overview")

        assert resp.status_code == 401
        app.dependency_overrides.clear()

    def test_authenticated_non_founder_gets_404_not_403(self, db_session, monkeypatch):
        """404, not 403 — matches this API's existing convention of not
        confirming a resource exists to someone not entitled to see it
        (documentation/API.md's cross-tenant rule). A curious business owner
        who finds this URL learns nothing from the response."""
        _business(db_session, "A")
        db_session.commit()
        monkeypatch.setattr(settings, "founder_clerk_user_ids", "the-real-founder")
        client = _client(db_session, claims_for_token=lambda t: {"sub": "some-business-owner"})

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        assert resp.status_code == 404
        app.dependency_overrides.clear()

    def test_empty_allowlist_denies_everyone(self, db_session, monkeypatch):
        """The safe default: an unconfigured allowlist means the feature is
        off for everyone, not open to everyone."""
        _business(db_session, "A")
        db_session.commit()
        monkeypatch.setattr(settings, "founder_clerk_user_ids", "")
        client = _client(db_session, claims_for_token=lambda t: {"sub": "anyone"})

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        assert resp.status_code == 404
        app.dependency_overrides.clear()

    def test_allowlisted_founder_is_admitted(self, db_session, monkeypatch):
        _business(db_session, "A")
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        assert resp.status_code == 200
        app.dependency_overrides.clear()

    def test_allowlist_supports_multiple_comma_separated_ids(self, db_session, monkeypatch):
        _business(db_session, "A")
        db_session.commit()
        monkeypatch.setattr(settings, "founder_clerk_user_ids", "founder-a, founder-b ,founder-c")
        client = _client(db_session, claims_for_token=lambda t: {"sub": "founder-b"})

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        assert resp.status_code == 200
        app.dependency_overrides.clear()

    def test_no_write_endpoints_exist(self, db_session, monkeypatch):
        """Read-only was an explicit requirement — guard against a future
        accidental mutation route slipping onto this router unreviewed."""
        client = _founder_client(db_session, monkeypatch)

        resp = client.post("/api/v1/founder/overview", headers=_auth())

        assert resp.status_code == 405
        app.dependency_overrides.clear()


class TestFounderOverviewAggregates:
    def test_covers_every_business_not_just_one(self, db_session, monkeypatch):
        """The one place cross-tenant visibility is correct, not a bug."""
        _business(db_session, "A")
        _business(db_session, "B")
        _business(db_session, "C")
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        data = resp.json()["data"]
        assert data["summary"]["total_businesses"] == 3
        assert {b["name"] for b in data["businesses"]} == {"A", "B", "C"}
        app.dependency_overrides.clear()

    def test_connected_and_onboarding_complete_flags(self, db_session, monkeypatch):
        connected = _business(
            db_session,
            "Connected Co",
            whatsapp_connection_status="connected",
            onboarding_status="live",
        )
        db_session.add(
            KbEntry(business_id=connected.id, title="Hours", content="9-5", status="published")
        )
        _business(db_session, "Not Connected Co")
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        rows = {b["name"]: b for b in resp.json()["data"]["businesses"]}
        assert rows["Connected Co"]["whatsapp"]["status"] == "connected"
        assert rows["Connected Co"]["onboarding_complete"] is True
        assert rows["Not Connected Co"]["whatsapp"]["status"] == "not_connected"
        assert rows["Not Connected Co"]["onboarding_complete"] is False
        assert resp.json()["data"]["summary"]["connected_businesses"] == 1
        app.dependency_overrides.clear()

    def test_knowledge_base_counts_published_and_draft_separately(self, db_session, monkeypatch):
        biz = _business(db_session, "KB Co")
        db_session.add(KbEntry(business_id=biz.id, title="A", content="x", status="published"))
        db_session.add(KbEntry(business_id=biz.id, title="B", content="x", status="published"))
        db_session.add(KbEntry(business_id=biz.id, title="C", content="x", status="draft"))
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        kb = resp.json()["data"]["businesses"][0]["knowledge_base"]
        assert kb["published_count"] == 2
        assert kb["draft_count"] == 1
        app.dependency_overrides.clear()

    def test_missing_knowledge_base_alert_fires_on_drafts_only(self, db_session, monkeypatch):
        """A business with only unreviewed drafts must still be flagged —
        nothing publishable exists yet, regardless of draft count."""
        biz = _business(db_session, "Drafts Only Co")
        db_session.add(KbEntry(business_id=biz.id, title="A", content="x", status="draft"))
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        assert "missing_knowledge_base" in resp.json()["data"]["businesses"][0]["alerts"]
        app.dependency_overrides.clear()

    def test_ai_activity_counts_and_credential_status(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
        biz = _business(db_session, "Active Co")
        db_session.flush()
        store_credentials(db_session, biz.id, access_token="tok", app_secret="sec")
        conv = _conversation(db_session, biz)
        now = _now()
        _message(db_session, conv, biz, direction="inbound", created_at=now - timedelta(minutes=5))
        _message(db_session, conv, biz, direction="outbound", created_at=now - timedelta(minutes=4))
        _message(
            db_session,
            conv,
            biz,
            direction="outbound",
            created_at=now - timedelta(minutes=1),
            msg_status="failed",
        )
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        row = resp.json()["data"]["businesses"][0]
        assert row["whatsapp"]["credential_stored"] is True
        assert row["ai_activity"]["conversations"] == 1
        assert row["ai_activity"]["ai_responses"] == 2  # both outbound messages
        assert row["ai_activity"]["failed_responses"] == 1
        assert "ai_failures" in row["alerts"]  # the failure is recent (1 min ago)
        app.dependency_overrides.clear()

    def test_ai_failures_alert_ignores_old_failures(self, db_session, monkeypatch):
        biz = _business(db_session, "Old Failure Co")
        conv = _conversation(db_session, biz)
        _message(
            db_session,
            conv,
            biz,
            direction="outbound",
            created_at=_now() - timedelta(days=3),
            msg_status="failed",
        )
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        row = resp.json()["data"]["businesses"][0]
        assert row["ai_activity"]["failed_responses"] == 1  # still counted in the all-time total
        assert "ai_failures" not in row["alerts"]  # but not flagged as a *current* problem
        app.dependency_overrides.clear()

    def test_average_response_time_computed_from_real_turns(self, db_session, monkeypatch):
        biz = _business(db_session, "Timed Co")
        conv = _conversation(db_session, biz)
        now = _now()
        _message(
            db_session, conv, biz, direction="inbound", created_at=now - timedelta(seconds=100)
        )
        _message(
            db_session, conv, biz, direction="outbound", created_at=now - timedelta(seconds=40)
        )  # 60s reply
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        data = resp.json()["data"]
        row = data["businesses"][0]
        assert row["ai_activity"]["avg_response_time_seconds"] == 60.0
        assert data["summary"]["avg_response_time_seconds"] == 60.0
        app.dependency_overrides.clear()

    def test_response_time_ignores_outbound_not_preceded_by_inbound(self, db_session, monkeypatch):
        """Two outbound messages in a row (e.g. a template + a follow-up)
        must not be counted as a "response" to each other."""
        biz = _business(db_session, "No Turn Co")
        conv = _conversation(db_session, biz)
        now = _now()
        _message(
            db_session, conv, biz, direction="outbound", created_at=now - timedelta(seconds=50)
        )
        _message(
            db_session, conv, biz, direction="outbound", created_at=now - timedelta(seconds=10)
        )
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        assert (
            resp.json()["data"]["businesses"][0]["ai_activity"]["avg_response_time_seconds"] is None
        )
        app.dependency_overrides.clear()

    def test_last_inbound_and_outbound_timestamps(self, db_session, monkeypatch):
        biz = _business(db_session, "Timestamps Co")
        conv = _conversation(db_session, biz)
        now = _now()
        inbound_at = now - timedelta(minutes=10)
        outbound_at = now - timedelta(minutes=9)
        _message(db_session, conv, biz, direction="inbound", created_at=inbound_at)
        _message(db_session, conv, biz, direction="outbound", created_at=outbound_at)
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        row = resp.json()["data"]["businesses"][0]
        # Sprint 77: to_iso_utc marks these naive-but-UTC values explicitly.
        assert row["whatsapp"]["last_inbound_at"] == inbound_at.isoformat() + "Z"
        assert row["whatsapp"]["last_outbound_at"] == outbound_at.isoformat() + "Z"
        assert row["last_activity_at"] == outbound_at.isoformat() + "Z"
        app.dependency_overrides.clear()

    def test_no_recent_activity_alert_only_applies_to_connected_businesses(
        self, db_session, monkeypatch
    ):
        stale_connected = _business(
            db_session, "Stale Connected Co", whatsapp_connection_status="connected"
        )
        conv = _conversation(db_session, stale_connected)
        _message(
            db_session,
            conv,
            stale_connected,
            direction="inbound",
            created_at=_now() - timedelta(days=30),
        )
        _business(db_session, "Never Connected Co")  # no messages, not connected
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        rows = {b["name"]: b for b in resp.json()["data"]["businesses"]}
        assert "no_recent_activity" in rows["Stale Connected Co"]["alerts"]
        # Not connected yet is already covered by whatsapp_disconnected —
        # piling on "no activity" for a business that was never live isn't
        # a meaningful, actionable signal.
        assert "no_recent_activity" not in rows["Never Connected Co"]["alerts"]
        assert "whatsapp_disconnected" in rows["Never Connected Co"]["alerts"]
        app.dependency_overrides.clear()

    def test_messages_today_excludes_older_messages(self, db_session, monkeypatch):
        biz = _business(db_session, "Today Co")
        conv = _conversation(db_session, biz)
        now = _now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        _message(
            db_session,
            conv,
            biz,
            direction="inbound",
            created_at=today_start + timedelta(minutes=1),
        )
        _message(
            db_session,
            conv,
            biz,
            direction="inbound",
            created_at=today_start - timedelta(minutes=1),
        )
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        assert resp.json()["data"]["summary"]["messages_today"] == 1
        app.dependency_overrides.clear()

    def test_businesses_are_ordered_newest_first(self, db_session, monkeypatch):
        older = _business(db_session, "Older Co")
        db_session.flush()
        older.created_at = _now() - timedelta(days=10)
        _business(db_session, "Newer Co")
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/overview", headers=_auth())

        names = [b["name"] for b in resp.json()["data"]["businesses"]]
        assert names.index("Newer Co") < names.index("Older Co")
        app.dependency_overrides.clear()


class TestAiMetrics:
    """Sprint 76, Objective B — app/services/founder_ops.py::get_ai_metrics."""

    def test_non_founder_gets_404(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "founder_clerk_user_ids", "the-real-founder")
        client = _client(db_session, claims_for_token=lambda t: {"sub": "someone-else"})

        resp = client.get("/api/v1/founder/ai-metrics", headers=_auth())

        assert resp.status_code == 404
        app.dependency_overrides.clear()

    def test_empty_platform_returns_zeroed_metrics(self, db_session, monkeypatch):
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/ai-metrics", headers=_auth())

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_turns"] == 0
        assert data["most_used_employee"] is None
        assert data["most_used_tools"] == []
        app.dependency_overrides.clear()

    def test_aggregates_employee_and_tool_usage_across_businesses(self, db_session, monkeypatch):
        biz_a = _business(db_session, "Clinic A")
        conv_a = _conversation(db_session, biz_a)
        biz_b = _business(db_session, "Clinic B")
        conv_b = _conversation(db_session, biz_b)

        _trace(
            db_session,
            biz_a,
            conv_a,
            steps=[{"domain": "calendar", "action": "calendar_booking", "role": "scheduler"}],
            proposed_tool_calls=[{"tool_name": "book_appointment", "agent_role": "scheduler"}],
            result_messages=[_result_message(db_session, conv_a, biz_a, status="sent")],
            duration_ms=200,
        )
        _trace(
            db_session,
            biz_b,
            conv_b,
            steps=[{"domain": "calendar", "action": "calendar_booking", "role": "scheduler"}],
            proposed_tool_calls=[{"tool_name": "book_appointment", "agent_role": "scheduler"}],
            result_messages=[_result_message(db_session, conv_b, biz_b, status="failed")],
            duration_ms=400,
        )
        _trace(
            db_session,
            biz_b,
            conv_b,
            category="conversation",
            clarification_hint="Missing a name for the lead.",
            result_messages=[_result_message(db_session, conv_b, biz_b, status="sent")],
            duration_ms=0,
        )
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/ai-metrics", headers=_auth())

        data = resp.json()["data"]
        assert data["total_turns"] == 3
        assert data["employee_utilisation"] == {"scheduler": 2}
        assert data["most_used_employee"] == "scheduler"
        assert data["most_used_tools"] == [{"tool_name": "book_appointment", "count": 2}]
        assert data["failed_tool_executions"] == 1  # only the trace whose result Message failed
        assert data["governance_blocks"] == 1  # the clarification_hint trace
        assert data["avg_plan_length"] == 2 / 3
        assert data["avg_execution_time_ms"] == 200.0
        app.dependency_overrides.clear()


class TestTraces:
    """Sprint 76, Objective C — Conversation Replay list/detail endpoints."""

    def test_non_founder_gets_404_for_list_and_detail(self, db_session, monkeypatch):
        monkeypatch.setattr(settings, "founder_clerk_user_ids", "the-real-founder")
        client = _client(db_session, claims_for_token=lambda t: {"sub": "someone-else"})

        assert client.get("/api/v1/founder/traces", headers=_auth()).status_code == 404
        assert (
            client.get(f"/api/v1/founder/traces/{uuid.uuid4()}", headers=_auth()).status_code == 404
        )
        app.dependency_overrides.clear()

    def test_list_orders_newest_first_and_summarizes_each_trace(self, db_session, monkeypatch):
        biz = _business(db_session, "Clinic A")
        conv = _conversation(db_session, biz)
        older = _trace(
            db_session,
            biz,
            conv,
            steps=[{"domain": "calendar", "action": "calendar_booking", "role": "scheduler"}],
            result_messages=[_result_message(db_session, conv, biz, status="sent")],
        )
        db_session.flush()
        older.created_at = _now() - timedelta(hours=1)
        newer = _trace(
            db_session,
            biz,
            conv,
            steps=[{"domain": "crm", "action": "crm_lead", "role": "sales_executive"}],
            result_messages=[_result_message(db_session, conv, biz, status="pending_approval")],
        )
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get("/api/v1/founder/traces", headers=_auth())

        assert resp.status_code == 200
        rows = resp.json()["data"]
        assert [r["id"] for r in rows] == [str(newer.id), str(older.id)]
        assert rows[0]["roles"] == ["sales_executive"]
        assert rows[0]["outcome"] == "pending_approval"
        assert rows[1]["outcome"] == "sent"
        app.dependency_overrides.clear()

    def test_list_filters_by_business_id(self, db_session, monkeypatch):
        biz_a = _business(db_session, "Clinic A")
        conv_a = _conversation(db_session, biz_a)
        biz_b = _business(db_session, "Clinic B")
        conv_b = _conversation(db_session, biz_b)
        _trace(db_session, biz_a, conv_a)
        _trace(db_session, biz_b, conv_b)
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get(
            "/api/v1/founder/traces", params={"business_id": str(biz_a.id)}, headers=_auth()
        )

        rows = resp.json()["data"]
        assert len(rows) == 1
        assert rows[0]["business_id"] == str(biz_a.id)
        app.dependency_overrides.clear()

    def test_detail_includes_customer_message_plan_and_result_messages(
        self, db_session, monkeypatch
    ):
        biz = _business(db_session, "Clinic A")
        conv = _conversation(db_session, biz)
        trigger = Message(
            conversation_id=conv.id,
            business_id=biz.id,
            direction="inbound",
            body="Book a cleaning tomorrow at 2pm",
            status="received",
        )
        db_session.add(trigger)
        db_session.flush()
        result = _result_message(db_session, conv, biz, status="sent", body="Booked!")
        trace = _trace(
            db_session,
            biz,
            conv,
            steps=[{"domain": "calendar", "action": "calendar_booking", "role": "scheduler"}],
            proposed_tool_calls=[{"tool_name": "book_appointment", "agent_role": "scheduler"}],
            result_messages=[result],
            trigger_message_id=trigger.id,
        )
        db_session.commit()
        client = _founder_client(db_session, monkeypatch)

        resp = client.get(f"/api/v1/founder/traces/{trace.id}", headers=_auth())

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["customer_message"] == "Book a cleaning tomorrow at 2pm"
        assert data["plan"]["steps"][0]["role"] == "scheduler"
        assert data["proposed_tool_calls"] == [
            {"tool_name": "book_appointment", "agent_role": "scheduler"}
        ]
        assert data["result_messages"][0]["body"] == "Booked!"
        assert data["outcome"] == "sent"
        app.dependency_overrides.clear()

    def test_detail_404_for_unknown_trace(self, db_session, monkeypatch):
        client = _founder_client(db_session, monkeypatch)

        resp = client.get(f"/api/v1/founder/traces/{uuid.uuid4()}", headers=_auth())

        assert resp.status_code == 404
        app.dependency_overrides.clear()
