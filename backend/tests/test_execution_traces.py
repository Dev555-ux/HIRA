"""Tests for app/services/execution_traces.py (Sprint 76) — the write-once
trace helper and the read helpers Founder Ops/Evaluation build on."""

import uuid
from datetime import datetime, timedelta, timezone

from app.ai.intent import ConversationCategory
from app.ai.plan import ExecutionPlan, PlanStep
from app.models import Business, Conversation, Customer, ExecutionTrace, Message
from app.services.execution_traces import (
    get_result_messages,
    get_trace,
    list_traces,
    record_execution_trace,
    resolve_outcome,
)


def _business(db, name="Clinic A") -> Business:
    biz = Business(name=name)
    db.add(biz)
    db.flush()
    return biz


def _conversation(db, business) -> Conversation:
    customer = Customer(business_id=business.id, wa_phone="+15550001111")
    db.add(customer)
    db.flush()
    conversation = Conversation(business_id=business.id, customer_id=customer.id)
    db.add(conversation)
    db.flush()
    return conversation


def _message(db, conversation, business, *, status="sent") -> Message:
    message = Message(
        conversation_id=conversation.id,
        business_id=business.id,
        direction="outbound",
        body="hi",
        status=status,
    )
    db.add(message)
    db.flush()
    return message


class TestRecordExecutionTrace:
    def test_persists_every_field_from_the_plan_and_arguments(self, db_session):
        biz = _business(db_session)
        conv = _conversation(db_session, biz)
        result_message = _message(db_session, conv, biz)
        plan = ExecutionPlan(
            category=ConversationCategory.ACTION,
            steps=(
                PlanStep(
                    domain="calendar",
                    action="calendar_booking",
                    role="scheduler",
                    tools=(),
                ),
            ),
        )

        trace = record_execution_trace(
            db_session,
            business_id=biz.id,
            conversation_id=conv.id,
            trigger_message_id=None,
            plan=plan,
            proposed_tool_calls=[{"tool_name": "book_appointment", "agent_role": "scheduler"}],
            result_message_ids=[result_message.id],
            duration_ms=123,
        )

        assert trace.id is not None
        assert trace.business_id == biz.id
        assert trace.conversation_id == conv.id
        assert trace.trigger_message_id is None
        assert trace.category == "action"
        assert trace.plan == {
            "category": "action",
            "steps": [
                {
                    "domain": "calendar",
                    "action": "calendar_booking",
                    "role": "scheduler",
                    "tools": [],
                }
            ],
            "clarification_hint": None,
            "active_domain": None,
        }
        assert trace.proposed_tool_calls == [
            {"tool_name": "book_appointment", "agent_role": "scheduler"}
        ]
        assert trace.result_message_ids == [str(result_message.id)]
        assert trace.duration_ms == 123

    def test_flushes_but_does_not_commit(self, db_session):
        """Callers persist the trace atomically with the Message rows it
        describes (Sprint 76's write-once design) — record_execution_trace
        must never commit on its own."""
        biz = _business(db_session)
        conv = _conversation(db_session, biz)
        plan = ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())

        record_execution_trace(
            db_session,
            business_id=biz.id,
            conversation_id=conv.id,
            trigger_message_id=None,
            plan=plan,
            proposed_tool_calls=[],
            result_message_ids=[],
            duration_ms=0,
        )
        db_session.rollback()

        assert db_session.query(ExecutionTrace).count() == 0


class TestGetTrace:
    def test_returns_the_trace_when_no_business_scope_given(self, db_session):
        biz = _business(db_session)
        conv = _conversation(db_session, biz)
        plan = ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())
        trace = record_execution_trace(
            db_session,
            business_id=biz.id,
            conversation_id=conv.id,
            trigger_message_id=None,
            plan=plan,
            proposed_tool_calls=[],
            result_message_ids=[],
            duration_ms=0,
        )
        db_session.commit()

        assert get_trace(db_session, trace.id) is not None

    def test_returns_none_for_an_unknown_id(self, db_session):
        assert get_trace(db_session, uuid.uuid4()) is None

    def test_returns_none_when_scoped_to_a_different_business(self, db_session):
        biz = _business(db_session, "Clinic A")
        other_biz = _business(db_session, "Clinic B")
        conv = _conversation(db_session, biz)
        plan = ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())
        trace = record_execution_trace(
            db_session,
            business_id=biz.id,
            conversation_id=conv.id,
            trigger_message_id=None,
            plan=plan,
            proposed_tool_calls=[],
            result_message_ids=[],
            duration_ms=0,
        )
        db_session.commit()

        assert get_trace(db_session, trace.id, business_id=other_biz.id) is None
        assert get_trace(db_session, trace.id, business_id=biz.id) is not None


class TestListTraces:
    def test_orders_newest_first(self, db_session):
        biz = _business(db_session)
        conv = _conversation(db_session, biz)
        plan = ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())
        older = record_execution_trace(
            db_session,
            business_id=biz.id,
            conversation_id=conv.id,
            trigger_message_id=None,
            plan=plan,
            proposed_tool_calls=[],
            result_message_ids=[],
            duration_ms=0,
        )
        db_session.flush()
        older.created_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
        newer = record_execution_trace(
            db_session,
            business_id=biz.id,
            conversation_id=conv.id,
            trigger_message_id=None,
            plan=plan,
            proposed_tool_calls=[],
            result_message_ids=[],
            duration_ms=0,
        )
        db_session.commit()

        traces = list_traces(db_session)

        assert [t.id for t in traces] == [newer.id, older.id]

    def test_filters_by_business_id(self, db_session):
        biz_a = _business(db_session, "Clinic A")
        biz_b = _business(db_session, "Clinic B")
        conv_a = _conversation(db_session, biz_a)
        conv_b = _conversation(db_session, biz_b)
        plan = ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())
        record_execution_trace(
            db_session,
            business_id=biz_a.id,
            conversation_id=conv_a.id,
            trigger_message_id=None,
            plan=plan,
            proposed_tool_calls=[],
            result_message_ids=[],
            duration_ms=0,
        )
        record_execution_trace(
            db_session,
            business_id=biz_b.id,
            conversation_id=conv_b.id,
            trigger_message_id=None,
            plan=plan,
            proposed_tool_calls=[],
            result_message_ids=[],
            duration_ms=0,
        )
        db_session.commit()

        traces = list_traces(db_session, business_id=biz_a.id)

        assert len(traces) == 1
        assert traces[0].business_id == biz_a.id

    def test_respects_limit_and_offset(self, db_session):
        biz = _business(db_session)
        conv = _conversation(db_session, biz)
        plan = ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())
        for _ in range(3):
            record_execution_trace(
                db_session,
                business_id=biz.id,
                conversation_id=conv.id,
                trigger_message_id=None,
                plan=plan,
                proposed_tool_calls=[],
                result_message_ids=[],
                duration_ms=0,
            )
        db_session.commit()

        assert len(list_traces(db_session, limit=2)) == 2
        assert len(list_traces(db_session, limit=2, offset=2)) == 1


class TestGetResultMessages:
    def test_resolves_ids_to_current_messages_in_order(self, db_session):
        biz = _business(db_session)
        conv = _conversation(db_session, biz)
        first = _message(db_session, conv, biz, status="pending_approval")
        second = _message(db_session, conv, biz, status="sent")
        plan = ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())
        trace = record_execution_trace(
            db_session,
            business_id=biz.id,
            conversation_id=conv.id,
            trigger_message_id=None,
            plan=plan,
            proposed_tool_calls=[],
            result_message_ids=[first.id, second.id],
            duration_ms=0,
        )
        db_session.commit()

        # The whole point of the write-once design: a status change *after*
        # the trace was recorded is reflected when resolved, not frozen at
        # trace-write time.
        first.status = "sent"
        db_session.commit()

        messages = get_result_messages(db_session, trace)

        assert [m.id for m in messages] == [first.id, second.id]
        assert messages[0].status == "sent"

    def test_returns_empty_list_for_a_trace_with_no_results(self, db_session):
        biz = _business(db_session)
        conv = _conversation(db_session, biz)
        plan = ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())
        trace = record_execution_trace(
            db_session,
            business_id=biz.id,
            conversation_id=conv.id,
            trigger_message_id=None,
            plan=plan,
            proposed_tool_calls=[],
            result_message_ids=[],
            duration_ms=0,
        )
        db_session.commit()

        assert get_result_messages(db_session, trace) == []


class TestResolveOutcome:
    def test_no_result_for_an_empty_list(self):
        assert resolve_outcome([]) == "no_result"

    def test_sent_when_every_message_is_sent(self):
        messages = [Message(status="sent"), Message(status="sent")]
        assert resolve_outcome(messages) == "sent"

    def test_failed_takes_priority_over_sent(self):
        messages = [Message(status="sent"), Message(status="failed")]
        assert resolve_outcome(messages) == "failed"

    def test_pending_approval_takes_priority_over_sending(self):
        messages = [Message(status="sending"), Message(status="pending_approval")]
        assert resolve_outcome(messages) == "pending_approval"

    def test_escalated_takes_priority_over_rejected(self):
        messages = [Message(status="rejected"), Message(status="escalated")]
        assert resolve_outcome(messages) == "escalated"
