"""Sprint 80 (multi-turn intent continuity, DEC-049) — regression coverage
for the production bug: a natural affirmative follow-up ("Sure, please go
ahead") lost all conversational context and the model narrated an action it
never had a tool to take.

Two layers:
- Pure, DB-free tests against app/ai/intent.py and app/ai/plan.py directly
  (no LLM, no database) — the actual classification/planning logic.
- DB-backed tests against app/services/execution_traces.py::get_pending_domain
  — the read-only lookup that turns a real conversation's history into the
  `pending_domain` plan.py consumes.
"""

from app.ai.intent import ConversationCategory, classify_conversation, domains_for_action
from app.ai.lead_tools import CREATE_LEAD
from app.ai.plan import ExecutionPlan, PlanStep, build_execution_plan
from app.ai.tools import (
    BOOK_APPOINTMENT,
    CANCEL_APPOINTMENT,
    CHECK_AVAILABILITY,
    RESCHEDULE_APPOINTMENT,
)
from app.models import Business, Conversation, Customer
from app.services.execution_traces import (
    get_pending_action,
    get_pending_domain,
    record_execution_trace,
)


# --- Part A: pure classification/planning, no DB, no LLM -------------------


class TestBookingSingleTurn:
    def test_a_natural_desire_statement_with_no_generic_calendar_word_is_still_action(self):
        """The exact original-request half of the production bug: no
        "book"/"schedule"/"appointment" anywhere, just a named service and a
        time — must still resolve to ACTION/calendar, not fall through to a
        tools-less CONVERSATION turn."""
        text = "I'd like a teeth cleaning tomorrow around 3 PM."
        assert classify_conversation(text) is None  # ambiguous on its own — see intent.py

        plan = build_execution_plan(text)
        assert plan.category == ConversationCategory.ACTION
        assert plan.active_domain == "calendar"
        assert {t.name for t in plan.tools} == {
            BOOK_APPOINTMENT,
            CHECK_AVAILABILITY,
            RESCHEDULE_APPOINTMENT,
            CANCEL_APPOINTMENT,
        }

    def test_an_explicit_booking_verb_still_works_unchanged(self):
        """Existing behaviour, preserved byte-for-byte."""
        plan = build_execution_plan("Book a meeting tomorrow at 10am.")
        assert plan.category == ConversationCategory.ACTION
        assert plan.active_domain == "calendar"
        assert BOOK_APPOINTMENT in {t.name for t in plan.tools}


class TestBookingConfirmationFollowUp:
    def test_a_bare_confirmation_inherits_the_pending_calendar_domain(self):
        """The exact second half of the production bug."""
        # "book it" is deliberately excluded here — it starts with the
        # imperative verb "book" and already confidently self-classifies as
        # ACTION via the pre-existing rule, with no need for pending_domain
        # at all (proven separately in TestBookingSingleTurn).
        for reply in [
            "Sure, please go ahead.",
            "yes",
            "yes please",
            "go ahead",
            "please do",
            "sounds good",
            "confirm it",
            "that's fine",
            "continue",
        ]:
            assert classify_conversation(reply) is None, f"{reply!r} unexpectedly matched a rule"
            plan = build_execution_plan(reply, pending_domain="calendar")
            assert plan.category == ConversationCategory.ACTION, reply
            assert {t.name for t in plan.tools} == {
                BOOK_APPOINTMENT,
                CHECK_AVAILABILITY,
                RESCHEDULE_APPOINTMENT,
                CANCEL_APPOINTMENT,
            }, reply

    def test_a_bare_confirmation_with_no_pending_domain_stays_conversation(self):
        """No workflow was open — "yes" alone still means nothing; must not
        default to offering tools just because the text is ambiguous."""
        plan = build_execution_plan("yes please")
        assert plan.category == ConversationCategory.CONVERSATION
        assert plan.tools == []

    def test_a_confirmation_inherits_the_pending_crm_domain_just_as_well(self):
        plan = build_execution_plan("go ahead", pending_domain="crm")
        assert plan.category == ConversationCategory.ACTION
        assert CREATE_LEAD in {t.name for t in plan.tools}


class TestBookingRejection:
    def test_an_explicit_decline_overrides_the_pending_domain(self):
        """"No thanks" confidently matches small talk on its own — a
        confident classification always wins over an inherited domain."""
        plan = build_execution_plan("No thanks, I'll pass.", pending_domain="calendar")
        assert plan.category == ConversationCategory.CONVERSATION
        assert plan.tools == []

    def test_a_soft_negative_still_continues_the_workflow(self):
        """"That doesn't work for me" has no confident signal of its own —
        in context, this almost always means "try a different time/slot,"
        not "abandon the request," so it correctly continues rather than
        going tools-less."""
        text = "No, that doesn't work for me."
        assert classify_conversation(text) is None
        plan = build_execution_plan(text, pending_domain="calendar")
        assert plan.category == ConversationCategory.ACTION
        assert CHECK_AVAILABILITY in {t.name for t in plan.tools}


class TestBookingClarification:
    def test_an_incomplete_request_withholds_tools_but_records_the_active_domain(self):
        plan = build_execution_plan("Book a meeting.")
        assert plan.category == ConversationCategory.ACTION
        assert plan.steps == ()
        assert plan.clarification_hint is not None
        assert plan.active_domain == "calendar"  # withheld, but still recorded for continuity

    def test_supplying_the_missing_detail_next_turn_completes_via_pending_domain(self):
        """The customer answers HIRA's own clarifying question with just the
        missing detail — no "book"/"schedule" this time either."""
        text = "Tomorrow at 3pm."
        assert domains_for_action(text) == ["calendar"]  # time marker alone is enough (Stage 2)
        plan = build_execution_plan(text, pending_domain="calendar")
        assert plan.category == ConversationCategory.ACTION
        assert BOOK_APPOINTMENT in {t.name for t in plan.tools}


class TestCancellation:
    def test_single_turn_cancellation_unchanged(self):
        plan = build_execution_plan("Cancel my appointment for tomorrow.")
        assert plan.category == ConversationCategory.ACTION
        assert plan.active_domain == "calendar"

    def test_cancellation_confirmation_follow_up_inherits_the_domain(self):
        """Cancel is governance-gated (REQUIRES_CONFIRMATION) — HIRA's own
        first turn asks the customer to confirm rather than offering the
        tool outright, which is exactly the "active but no write proposed
        yet" pending shape. A bare "yes" (no repeated "cancel" keyword) has
        no domain match of its own, so this is intent continuity's job,
        not planning/readiness's — with no specific action identified from
        "yes" alone, all of calendar's tools come back as a pass-through
        (app/ai/planning.py's existing, documented behavior), including
        cancel_appointment. (A reply that repeats "cancel" without a date —
        "yes, cancel it" — re-triggers calendar_cancel's own readiness
        check, which is deliberately memory-less across turns by design
        (see app/ai/planning.py's docstring) — an intentional, pre-existing
        scope boundary Sprint 80 doesn't touch.)"""
        plan = build_execution_plan("yes", pending_domain="calendar")
        assert plan.category == ConversationCategory.ACTION
        assert CANCEL_APPOINTMENT in {t.name for t in plan.tools}


class TestReschedule:
    def test_single_turn_reschedule_unchanged(self):
        plan = build_execution_plan("Reschedule my appointment to tomorrow at 10am.")
        assert plan.category == ConversationCategory.ACTION
        assert plan.active_domain == "calendar"

    def test_reschedule_confirmation_follow_up_inherits_the_domain(self):
        plan = build_execution_plan("please do", pending_domain="calendar")
        assert plan.category == ConversationCategory.ACTION
        assert RESCHEDULE_APPOINTMENT in {t.name for t in plan.tools}


class TestLeadCreationAndCrmUpdates:
    def test_single_turn_lead_creation_unchanged(self):
        plan = build_execution_plan("Create a lead for John.")
        assert plan.category == ConversationCategory.ACTION
        assert plan.active_domain == "crm"

    def test_lead_creation_confirmation_follow_up_inherits_the_domain(self):
        plan = build_execution_plan("yes please", pending_domain="crm")
        assert plan.category == ConversationCategory.ACTION
        assert CREATE_LEAD in {t.name for t in plan.tools}


def test_invoice_and_quotation_sending_are_not_yet_product_features():
    """Requirement 5 asks for invoice/quotation-sending coverage — there is
    no such tool in app/ai/tools.py or app/ai/lead_tools.py today (only
    Calendar and CRM domains exist — see app/ai/intent.py's
    _ACTION_CATEGORIES). "Send an invoice" therefore still degrades to a
    plain-text reply, exactly as it did before this sprint — the continuity
    mechanism itself is domain-agnostic (get_pending_domain/active_domain
    don't hardcode "calendar"/"crm" anywhere) and will apply automatically
    the moment an Invoice/Quotation _ActionCategory is added, with no
    changes needed here."""
    plan = build_execution_plan("Send an invoice.")
    assert plan.category == ConversationCategory.ACTION
    assert plan.steps == ()
    assert plan.active_domain is None  # no domain exists to be "active"


class TestTopicSwitchesAndInterruptions:
    def test_a_confident_knowledge_question_overrides_a_pending_domain(self):
        plan = build_execution_plan("What are your opening hours?", pending_domain="calendar")
        assert plan.category == ConversationCategory.KNOWLEDGE
        assert plan.tools == []

    def test_a_confident_new_action_in_a_different_domain_overrides_the_pending_one(self):
        """Mid-booking, the customer pivots to a clearly-different, fully
        explicit request — the new one must win, not the stale one."""
        plan = build_execution_plan("Actually, create a lead for Priya.", pending_domain="calendar")
        assert plan.category == ConversationCategory.ACTION
        assert plan.active_domain == "crm"
        assert CREATE_LEAD in {t.name for t in plan.tools}

    def test_a_greeting_mid_workflow_clears_the_pending_domain(self):
        plan = build_execution_plan("Hi there!", pending_domain="calendar")
        assert plan.category == ConversationCategory.CONVERSATION
        assert plan.tools == []


class TestUnrelatedDisclosureDoesNotHijackAPendingDomain:
    """Sprint 81 (production bug fix, DEC-057): a real, reproduced bug — with
    a calendar domain left open by an earlier turn (booked, or merely
    discussed, a couple of turns back), an unrelated message like "My name is
    Devansh, just so you know." was silently treated as a continuation of
    that stale domain and got every one of its tools, including
    book_appointment, exposed with no readiness check and no governance gate
    (book_appointment/create_lead aren't governance-gated at all — see
    app/ai/tools.py::GOVERNED_TOOL_ACTIONS). Demo Chat (app/ai/playground.py)
    executes whatever the model then proposes immediately, with no human
    review, so this reliably produced a second, real, unrequested
    Appointment row. See app/ai/intent.py::is_unrelated_disclosure for the
    fix itself; this class is the regression coverage for it."""

    def test_the_reproduced_bug_no_longer_offers_booking_tools(self):
        """The exact live repro: pending_domain="calendar" with no
        pending_action (the prior turn already resolved, same shape as a
        booking that completed a couple of turns ago), then an unrelated
        self-disclosure. Before the fix, this returned all four calendar
        tools, including BOOK_APPOINTMENT."""
        plan = build_execution_plan("My name is Devansh.", pending_domain="calendar")
        assert plan.category == ConversationCategory.CONVERSATION
        assert plan.tools == []

    def test_the_reproduced_bug_exact_wording_no_longer_offers_booking_tools(self):
        """The literal sentence from the live reproduction."""
        plan = build_execution_plan(
            "My name is Devansh, just so you know.", pending_domain="calendar"
        )
        assert plan.category == ConversationCategory.CONVERSATION
        assert plan.tools == []

    def test_thank_you_mid_workflow_does_not_execute_a_tool(self):
        """Already worked before this fix (small talk is a confident Stage 1
        match, never reaches pending_domain at all) — kept here as an
        explicit regression check alongside the sibling cases above, per the
        bug's own required test list."""
        plan = build_execution_plan("Thank you.", pending_domain="calendar")
        assert plan.category == ConversationCategory.CONVERSATION
        assert plan.tools == []

    def test_an_unrelated_aside_mid_workflow_does_not_offer_tools(self):
        """Same shape, different unrelated content — the fix targets the
        pattern (an unprompted disclosure), not just the one reported
        sentence."""
        plan = build_execution_plan(
            "By the way, I really like your new website design.", pending_domain="calendar"
        )
        assert plan.category == ConversationCategory.CONVERSATION
        assert plan.tools == []

    def test_a_disclosure_clears_a_pending_crm_domain_too(self):
        """Not calendar-specific — the same stale-domain hijack was equally
        possible after a lead-creation turn."""
        plan = build_execution_plan("My name is Devansh, by the way.", pending_domain="crm")
        assert plan.category == ConversationCategory.CONVERSATION
        assert plan.tools == []

    def test_legitimate_booking_continuation_still_completes(self):
        """Must not regress: supplying the missing detail is still a real
        continuation, not a disclosure."""
        plan = build_execution_plan("Tomorrow at 3pm.", pending_domain="calendar")
        assert plan.category == ConversationCategory.ACTION
        assert BOOK_APPOINTMENT in {t.name for t in plan.tools}

    def test_legitimate_reschedule_correction_still_completes(self):
        plan = build_execution_plan("Actually make it 4pm.", pending_domain="calendar")
        assert plan.category == ConversationCategory.ACTION
        assert {BOOK_APPOINTMENT, RESCHEDULE_APPOINTMENT} & {t.name for t in plan.tools}

    def test_legitimate_lead_continuation_with_contact_info_still_completes(self):
        """Providing a follow-up detail for an already-open CRM workflow
        (an email address) must still expose the CRM tools, same as before
        this fix — only a genuinely unrelated disclosure is screened out."""
        plan = build_execution_plan("His email is john@example.com", pending_domain="crm")
        assert plan.category == ConversationCategory.ACTION
        assert CREATE_LEAD in {t.name for t in plan.tools}

    def test_bare_confirmations_are_unaffected_by_the_disclosure_check(self):
        """The fix must not regress DEC-049/DEC-051's own confirmation
        continuity — none of these contain a self-disclosure marker, so all
        must keep working exactly as TestBookingConfirmationFollowUp already
        proves elsewhere in this file."""
        for reply in ["Sure, please go ahead.", "yes", "go ahead", "sounds good", "continue"]:
            plan = build_execution_plan(reply, pending_domain="calendar")
            assert plan.category == ConversationCategory.ACTION, reply
            assert BOOK_APPOINTMENT in {t.name for t in plan.tools}, reply


def test_ambiguous_replies_never_hardcode_a_phrase_list():
    """Structural proof, not just behavioural: classify_conversation has no
    branch that matches any of these strings specifically — they all fall
    through to None on their own merit (no rule fires), and it's
    build_execution_plan's *caller-supplied* pending_domain, not a keyword
    table, that resolves them."""
    for reply in ["ok", "okay", "sure", "yep", "alright", "great", "perfect"]:
        assert classify_conversation(reply) is None, reply


# --- Part B: get_pending_domain against real ExecutionTrace rows -----------


def _business(db, name="Clinic A") -> Business:
    biz = Business(name=name)
    db.add(biz)
    db.flush()
    return biz


def _conversation(db, business, *, phone: str = "+15550001111") -> Conversation:
    customer = Customer(business_id=business.id, wa_phone=phone)
    db.add(customer)
    db.flush()
    conversation = Conversation(business_id=business.id, customer_id=customer.id)
    db.add(conversation)
    db.flush()
    return conversation


def _record(db, conversation, business, plan: ExecutionPlan, proposed_tool_calls: list[dict]):
    trace = record_execution_trace(
        db,
        business_id=business.id,
        conversation_id=conversation.id,
        trigger_message_id=None,
        plan=plan,
        proposed_tool_calls=proposed_tool_calls,
        result_message_ids=[],
        duration_ms=1,
    )
    db.commit()
    return trace


def test_get_pending_domain_returns_none_for_a_conversation_with_no_traces(db_session):
    biz = _business(db_session)
    conv = _conversation(db_session, biz)
    assert get_pending_domain(db_session, conv.id) is None


def test_get_pending_domain_finds_an_action_turn_with_no_proposed_write(db_session):
    """The exact shape of turn 1 in the production bug, once fixed: tools
    were offered (active_domain set) but the model's first response didn't
    call a write tool yet — still pending."""
    biz = _business(db_session)
    conv = _conversation(db_session, biz)
    plan = ExecutionPlan(category=ConversationCategory.ACTION, steps=(), active_domain="calendar")
    _record(db_session, conv, biz, plan, proposed_tool_calls=[])

    assert get_pending_domain(db_session, conv.id) == "calendar"


def test_get_pending_domain_is_none_once_a_write_tool_was_proposed(db_session):
    """Self-clearing: the moment a real write action is proposed, the next
    turn has nothing to inherit — a fresh, unrelated follow-up gets fresh
    classification instead of stale calendar tools forever."""
    biz = _business(db_session)
    conv = _conversation(db_session, biz)
    step = PlanStep(domain="calendar", action="calendar_booking", role="scheduler", tools=())
    plan = ExecutionPlan(
        category=ConversationCategory.ACTION, steps=(step,), active_domain="calendar"
    )
    _record(
        db_session,
        conv,
        biz,
        plan,
        proposed_tool_calls=[{"tool_name": BOOK_APPOINTMENT, "agent_role": "scheduler"}],
    )

    assert get_pending_domain(db_session, conv.id) is None


def test_get_pending_domain_is_none_for_a_non_action_turn(db_session):
    biz = _business(db_session)
    conv = _conversation(db_session, biz)
    plan = ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())
    _record(db_session, conv, biz, plan, proposed_tool_calls=[])

    assert get_pending_domain(db_session, conv.id) is None


def test_get_pending_domain_only_looks_at_the_single_most_recent_turn(db_session):
    """An old pending calendar turn, superseded by a later, fully-resolved
    CRM turn — the stale calendar domain must not leak back in."""
    biz = _business(db_session)
    conv = _conversation(db_session, biz)
    calendar_plan = ExecutionPlan(
        category=ConversationCategory.ACTION, steps=(), active_domain="calendar"
    )
    _record(db_session, conv, biz, calendar_plan, proposed_tool_calls=[])

    conversation_plan = ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())
    _record(db_session, conv, biz, conversation_plan, proposed_tool_calls=[])

    assert get_pending_domain(db_session, conv.id) is None


def test_get_pending_domain_is_scoped_to_its_own_conversation(db_session):
    biz = _business(db_session)
    conv_a = _conversation(db_session, biz, phone="+15550001111")
    conv_b = _conversation(db_session, biz, phone="+15550002222")
    plan = ExecutionPlan(category=ConversationCategory.ACTION, steps=(), active_domain="calendar")
    _record(db_session, conv_a, biz, plan, proposed_tool_calls=[])

    assert get_pending_domain(db_session, conv_a.id) == "calendar"
    assert get_pending_domain(db_session, conv_b.id) is None


# --- Part C: get_pending_action (DEC-051) against real ExecutionTrace rows -


def test_get_pending_action_returns_none_for_a_conversation_with_no_traces(db_session):
    biz = _business(db_session)
    conv = _conversation(db_session, biz)
    assert get_pending_action(db_session, conv.id) is None


def test_get_pending_action_finds_a_governance_gated_ready_action(db_session):
    """The exact shape of a turn governance withheld pending confirmation:
    steps empty (nothing offered yet), but pending_action names the
    already-validated action the next turn's confirmation should resume."""
    biz = _business(db_session)
    conv = _conversation(db_session, biz)
    plan = ExecutionPlan(
        category=ConversationCategory.ACTION,
        steps=(),
        active_domain="calendar",
        pending_action="calendar_cancel",
    )
    _record(db_session, conv, biz, plan, proposed_tool_calls=[])

    assert get_pending_action(db_session, conv.id) == "calendar_cancel"


def test_get_pending_action_is_none_once_the_action_was_actually_proposed(db_session):
    """Self-clearing, same as get_pending_domain: once a write tool is
    genuinely proposed, there's nothing left to resume."""
    biz = _business(db_session)
    conv = _conversation(db_session, biz)
    step = PlanStep(domain="calendar", action="calendar_cancel", role="scheduler", tools=())
    plan = ExecutionPlan(
        category=ConversationCategory.ACTION, steps=(step,), active_domain="calendar"
    )
    _record(
        db_session,
        conv,
        biz,
        plan,
        proposed_tool_calls=[{"tool_name": CANCEL_APPOINTMENT, "agent_role": "scheduler"}],
    )

    assert get_pending_action(db_session, conv.id) is None


def test_get_pending_action_is_none_when_no_action_was_pending(db_session):
    """A plain "no tools offered" turn (e.g. planning withheld for missing
    info, not governance) never has a pending_action to resume."""
    biz = _business(db_session)
    conv = _conversation(db_session, biz)
    plan = ExecutionPlan(category=ConversationCategory.ACTION, steps=(), active_domain="calendar")
    _record(db_session, conv, biz, plan, proposed_tool_calls=[])

    assert get_pending_action(db_session, conv.id) is None


def test_get_pending_action_only_looks_at_the_single_most_recent_turn(db_session):
    biz = _business(db_session)
    conv = _conversation(db_session, biz)
    gated_plan = ExecutionPlan(
        category=ConversationCategory.ACTION,
        steps=(),
        active_domain="calendar",
        pending_action="calendar_cancel",
    )
    _record(db_session, conv, biz, gated_plan, proposed_tool_calls=[])

    conversation_plan = ExecutionPlan(category=ConversationCategory.CONVERSATION, steps=())
    _record(db_session, conv, biz, conversation_plan, proposed_tool_calls=[])

    assert get_pending_action(db_session, conv.id) is None


def test_get_pending_action_is_scoped_to_its_own_conversation(db_session):
    biz = _business(db_session)
    conv_a = _conversation(db_session, biz, phone="+15550001111")
    conv_b = _conversation(db_session, biz, phone="+15550002222")
    plan = ExecutionPlan(
        category=ConversationCategory.ACTION,
        steps=(),
        active_domain="calendar",
        pending_action="calendar_cancel",
    )
    _record(db_session, conv_a, biz, plan, proposed_tool_calls=[])

    assert get_pending_action(db_session, conv_a.id) == "calendar_cancel"
    assert get_pending_action(db_session, conv_b.id) is None
