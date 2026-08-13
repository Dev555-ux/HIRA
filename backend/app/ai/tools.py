"""Booking + CRM tool definitions and dispatcher — the AI's calendar and lead
actions (DEC-032, DEC-033).

Tool schemas are passed to the LLM alongside the system prompt so the model
can propose booking/reschedule/cancel/CRM actions instead of only generating
text. `execute_tool_call()` is the only place a proposed action becomes a
real write, and it always goes through `AppointmentService`
(`app/calendar/factory.py`) for calendar tools or `app/ai/lead_tools.py` for
CRM tools, never a vendor SDK or data-access path of its own.

`check_availability` is read-only and always safe to execute immediately
(see `execute_check_availability`, used by `app/ai/orchestrator.py`). Every
other tool here — calendar and CRM alike — writes real state, so DEC-032/
DEC-033 gate all of them behind the existing Pending Approvals workflow in
Assisted Mode (see `app/ai/processing.py`); only Autonomous Mode, or an
already-approved pending draft, calls `execute_tool_call` for these.

Sprint 74 Phase 1 (DEC-043): `response_to_message_fields()` turns up to
`MAX_TOOL_CALLS_PER_TURN` (2) proposed actions from one LLMResponse into
that many independent Message rows, each governed/approved/executed exactly
as a single proposed action always was — "two employees acting in one
customer turn" is two ordinary tool-call Messages, not a new execution
path. `app/ai/intent.py`/`app/ai/planning.py`/`app/ai/governance.py` are
unchanged: they still offer/gate exactly one tool-schema category per turn,
so both entries (when there are two) come from that same already-governed
category — no action reaches here without having gone through the existing
governance gate.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from app.ai.governance import ExecutionDecision, evaluate_execution
from app.ai.lead_tools import (
    LEAD_TOOL_NAMES,
    LEAD_TOOL_SCHEMAS,
    execute_lead_tool_call,
    preview_lead_tool_call,
)
from app.ai.llm.base import LLMResponse, ToolCall, ToolSchema
from app.ai.tool_results import ToolExecutionResult
from app.calendar.factory import get_appointment_service
from app.calendar.providers.base import (
    CalendarAlreadyCancelledError,
    CalendarConflictError,
    CalendarError,
    CalendarValidationError,
)
from app.calendar.service import get_upcoming_appointments

logger = logging.getLogger(__name__)

CHECK_AVAILABILITY = "check_availability"
BOOK_APPOINTMENT = "book_appointment"
RESCHEDULE_APPOINTMENT = "reschedule_appointment"
CANCEL_APPOINTMENT = "cancel_appointment"

_CALENDAR_TOOL_SCHEMAS = [
    ToolSchema(
        name=CHECK_AVAILABILITY,
        description=(
            "Check which time slots are free on the business's calendar within a "
            "date/time range, before proposing a booking. Always call this before "
            "book_appointment unless the customer already confirmed a specific slot."
        ),
        interaction_type="read",
        parameters={
            "type": "object",
            "properties": {
                "starts_at": {
                    "type": "string",
                    "description": "ISO 8601 datetime, start of the range to check",
                },
                "ends_at": {
                    "type": "string",
                    "description": "ISO 8601 datetime, end of the range to check",
                },
            },
            "required": ["starts_at", "ends_at"],
        },
    ),
    ToolSchema(
        name=BOOK_APPOINTMENT,
        description=(
            "Propose booking a new appointment for the customer, once a specific "
            "free slot has been confirmed with them. This does not send immediately"
            " — a human reviews it first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "starts_at": {
                    "type": "string",
                    "description": "ISO 8601 datetime the appointment starts",
                },
                "ends_at": {
                    "type": "string",
                    "description": "ISO 8601 datetime the appointment ends",
                },
                "summary": {
                    "type": "string",
                    "description": "Short description, e.g. 'Dental cleaning'",
                },
            },
            "required": ["starts_at", "ends_at", "summary"],
        },
    ),
    ToolSchema(
        name=RESCHEDULE_APPOINTMENT,
        description="Propose moving the customer's existing upcoming appointment to a new time.",
        parameters={
            "type": "object",
            "properties": {
                "starts_at": {"type": "string", "description": "New ISO 8601 start datetime"},
                "ends_at": {"type": "string", "description": "New ISO 8601 end datetime"},
            },
            "required": ["starts_at", "ends_at"],
        },
    ),
    ToolSchema(
        name=CANCEL_APPOINTMENT,
        description="Propose cancelling the customer's existing upcoming appointment.",
        parameters={"type": "object", "properties": {}},
    ),
]

TOOL_SCHEMAS = [*_CALENDAR_TOOL_SCHEMAS, *LEAD_TOOL_SCHEMAS]

# Sprint 57: exposed (was module-private) so app/ai/intent.py's tool-category
# registry can select this group directly instead of redefining it.
CALENDAR_TOOL_SCHEMAS = _CALENDAR_TOOL_SCHEMAS

# DEC-050: every read-only tool across every domain, derived from the
# schemas themselves rather than a hardcoded name list — lets
# app/ai/orchestrator.py's bounded round-trip generalize past calendar's
# check_availability without ever needing to know a tool's name or domain.
READ_TOOL_NAMES = {schema.name for schema in TOOL_SCHEMAS if schema.interaction_type == "read"}


def preview_tool_call(tool_call: ToolCall) -> str:
    """Human-readable, editable preview shown in the Pending queue before approval."""
    if tool_call.name in LEAD_TOOL_NAMES:
        return preview_lead_tool_call(tool_call)
    args = tool_call.arguments
    if tool_call.name == BOOK_APPOINTMENT:
        return (
            f"Book: {args.get('summary', 'Appointment')} "
            f"({args.get('starts_at', '?')} – {args.get('ends_at', '?')})"
        )
    if tool_call.name == RESCHEDULE_APPOINTMENT:
        return f"Reschedule your appointment to {args.get('starts_at', '?')} – {args.get('ends_at', '?')}"
    if tool_call.name == CANCEL_APPOINTMENT:
        return "Cancel your upcoming appointment"
    return f"{tool_call.name}({args})"


def confirmation_message_for(tool_call: ToolCall, result: ToolExecutionResult) -> str:
    """Deterministic, customer-facing text sent in Autonomous Mode after a
    tool call executes successfully (Section A1 fix) — never
    preview_tool_call()'s internal, editable-in-the-dashboard text. No LLM
    call: built only from the tool name, its arguments, and the execution
    result. Assisted Mode never calls this — see app/ai/processing.py's
    _auto_send, the only call site.
    """
    args = tool_call.arguments
    if tool_call.name == BOOK_APPOINTMENT:
        return (
            f"You're all set! {args.get('summary', 'Your appointment')} is booked "
            f"for {args.get('starts_at', '?')} to {args.get('ends_at', '?')}."
        )
    if tool_call.name == RESCHEDULE_APPOINTMENT:
        return (
            f"Your appointment has been rescheduled to "
            f"{args.get('starts_at', '?')} – {args.get('ends_at', '?')}."
        )
    if tool_call.name == CANCEL_APPOINTMENT:
        return "Your appointment has been cancelled."
    # CRM tools (create_lead, update_lead_stage, set_lead_follow_up) are
    # internal bookkeeping with nothing appointment-specific to confirm.
    return "Thanks — that's been taken care of."


# Sprint 83 (production bug fix, DEC-059): natural, customer-facing phrasing
# for the calendar failure reasons execute_tool_call tags below — keyed by
# ToolExecutionResult.reason, never by pattern-matching result.message
# itself. A reason with no entry here (a CRM failure, or a CalendarError
# subtype this doesn't have specific wording for yet, e.g.
# CalendarProviderUnavailableError) falls through to result.message
# unchanged in failure_message_for — today's existing behavior for those,
# not something this fix touches.
_FAILURE_MESSAGES: dict[str, str] = {
    "conflict": (
        "That time isn't available because it overlaps another appointment. "
        "Would you like to choose another time?"
    ),
    "needs_confirmation": (
        "I need your confirmation before making that change. Would you like me to proceed?"
    ),
    "not_found": (
        "I couldn't find an upcoming appointment to change. Can you tell me which appointment you mean?"
    ),
    "already_cancelled": (
        "That appointment has already been cancelled. Would you like to book a new one instead?"
    ),
    "invalid_request": "That time doesn't work — could you try a different date or time?",
}


def failure_message_for(result: ToolExecutionResult) -> str:
    """Customer-facing text for a failed tool call — the failure-path
    counterpart to confirmation_message_for above. `result.message` is
    written for logs/execution traces/founder-facing surfaces (e.g.
    "Requested slot overlaps an existing appointment", or a governance
    policy string) and must never be sent to a customer directly; this is
    the one place that translates a tagged `result.reason` into something
    HIRA would actually say. Falls back to `result.message` unchanged when
    there's no reason, or no mapping for it yet — today's existing
    behavior, not a regression, for any failure this fix doesn't cover."""
    if result.reason is not None and result.reason in _FAILURE_MESSAGES:
        return _FAILURE_MESSAGES[result.reason]
    return result.message


#: Sprint 74 Phase 1 (DEC-043): the model may propose more than one action in
#: a single response; at most this many are ever turned into Message rows.
#: Not configurable yet, and not a general multi-tool-execution engine — see
#: this module's own docstring and DEC-043 for why 2, not unbounded.
MAX_TOOL_CALLS_PER_TURN = 2


# Critical audit fix (governance bypass): every tool name here is checked
# against app/ai/governance.py's policy for the mapped action *inside*
# execute_tool_call — the one real chokepoint where a proposed action
# becomes a write (see this module's own docstring) — instead of relying
# only on app/ai/plan.py offering/withholding the tool schema in the first
# place. app/ai/plan.py's classification is deliberately permissive (a
# domain match with no specific action still offers every tool in that
# domain — see its own tests) and was never meant to be the sole safety net
# for a destructive action; this dict is. A future destructive tool becomes
# governed by adding one entry here, pointing at its
# app/ai/governance.py::_POLICIES action name — no other code changes.
GOVERNED_TOOL_ACTIONS: dict[str, str] = {
    RESCHEDULE_APPOINTMENT: "calendar_reschedule",
    CANCEL_APPOINTMENT: "calendar_cancel",
}


def response_to_message_fields(response: LLMResponse) -> list[tuple[str, str, dict]]:
    """[(type, body, extra_ai_meta), ...] for storing an LLMResponse as one or
    more Message rows — one entry per proposed action, capped at
    MAX_TOOL_CALLS_PER_TURN (Sprint 74 Phase 1). Always at least one entry.

    Shared by app/ai/processing.py (initial generation), app/ai/playground.py
    (Demo Chat), and app/services/replies.py (regenerate — which only ever
    consumes the first entry, since it replaces one already-existing Message;
    see its own docstring), so every caller interprets a response the same
    way.

    Employee attribution (ai_meta["agent_role"]) is deliberately NOT added
    here — app/ai/roles.py imports tool name constants from this module, so
    importing app/ai/roles.py back here would be circular. Callers attach
    agent_role via app.ai.roles.role_for_tool(tool_name) when building the
    final ai_meta dict.
    """
    if not response.tool_calls:
        return [("text", response.text, {})]

    fields: list[tuple[str, str, dict]] = []
    for tool_call in response.tool_calls[:MAX_TOOL_CALLS_PER_TURN]:
        if tool_call.name == CHECK_AVAILABILITY:
            # check_availability is read-only and meant to be resolved
            # entirely inside generate_reply()'s bounded round-trip
            # (app/ai/orchestrator.py). Reaching here means the model asked
            # again after that round-trip (observed live with Groq/Llama on
            # an unconnected calendar) — there's nothing meaningful to
            # approve for a read-only lookup, so this contributes no entry
            # of its own rather than surfacing a confusing "pending"
            # availability check that approve_and_send couldn't execute
            # anyway. Unlike before Sprint 74, this no longer short-circuits
            # the whole response — a second, real tool call alongside it
            # (if any) still gets its own entry below.
            continue
        fields.append(
            (
                "tool_call",
                preview_tool_call(tool_call),
                {"tool_name": tool_call.name, "tool_arguments": tool_call.arguments},
            )
        )

    if not fields:
        # Every proposed call was check_availability (or tool_calls was
        # empty after slicing, which can't actually happen) — same fallback
        # text as before Sprint 74.
        return [("text", response.text or "Let me check on that and get back to you.", {})]
    return fields


def execute_tool_call(
    db: Session,
    business_id: uuid.UUID,
    tool_call: ToolCall,
    *,
    customer_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    commit: bool = True,
    pending_action: str | None = None,
    human_approved: bool = False,
) -> ToolExecutionResult:
    """Executes a write tool (calendar or CRM) for real.

    Never call this for check_availability — see execute_check_availability.

    `commit=True` (default): every write commits immediately inside its own
    service call, exactly as before. `commit=False` (Section A4): passed
    through to book_appointment/create_lead/update_lead so none of them
    commit — the caller (app/services/replies.py::approve_and_send,
    app/ai/processing.py::_auto_send) persists this tool's effect and its
    own Message update in one atomic commit instead. reschedule_appointment
    and cancel_appointment are unaffected — out of scope for A4, they keep
    committing internally regardless of `commit`.

    Governance (critical audit fix): for a tool in GOVERNED_TOOL_ACTIONS,
    this refuses to execute unless the caller proves confirmation — either
    `human_approved=True` (a human explicitly approved this exact tool call
    in Assisted Mode's dashboard, which is itself a valid confirmation, and
    satisfies even a REQUIRES_HUMAN_APPROVAL-tier policy) or `pending_action`
    equals the tool's mapped action (the conversation already went through
    governance.py's REQUIRES_CONFIRMATION flow in a prior turn — see
    app/services/execution_traces.py::get_pending_action). Callers fetch
    `pending_action` themselves (a cheap, read-only lookup); this function
    only judges it, never derives it from `tool_call` or from how the
    calling turn was classified — that independence from intent
    classification is the entire point of gating here rather than only in
    app/ai/plan.py.
    """
    governed_action = GOVERNED_TOOL_ACTIONS.get(tool_call.name)
    if governed_action is not None and not human_approved:
        decision = evaluate_execution(governed_action).decision
        confirmed_by_customer = (
            decision == ExecutionDecision.REQUIRES_CONFIRMATION
            and pending_action == governed_action
        )
        if decision != ExecutionDecision.EXECUTE_NOW and not confirmed_by_customer:
            logger.warning(
                "Refused to execute %s for business %s: governance policy for '%s' is "
                "%s and no confirmation (human approval or a matching prior-turn "
                "pending_action) was established.",
                tool_call.name,
                business_id,
                governed_action,
                decision.value,
            )
            return ToolExecutionResult(
                False,
                "This action needs to be confirmed with the customer before it can be completed.",
                reason="needs_confirmation",
            )

    if tool_call.name in LEAD_TOOL_NAMES:
        return execute_lead_tool_call(
            db, business_id, tool_call, customer_id=customer_id, commit=commit
        )

    try:
        appointment_service = get_appointment_service(db, business_id)

        if tool_call.name == BOOK_APPOINTMENT:
            appointment = appointment_service.book_appointment(
                customer_id=customer_id,
                conversation_id=conversation_id,
                starts_at=datetime.fromisoformat(tool_call.arguments["starts_at"]),
                ends_at=datetime.fromisoformat(tool_call.arguments["ends_at"]),
                summary=tool_call.arguments.get("summary", "Appointment"),
                commit=commit,
            )
            on_commit_failure = (
                None
                if commit
                else (
                    lambda: appointment_service.cancel_calendar_event(appointment.google_event_id)
                )
            )
            return ToolExecutionResult(
                True, "Appointment booked.", appointment.id, on_commit_failure=on_commit_failure
            )

        if tool_call.name in (RESCHEDULE_APPOINTMENT, CANCEL_APPOINTMENT):
            # A WhatsApp customer doesn't know their appointment's internal id,
            # so reschedule/cancel resolve "the customer's next upcoming
            # appointment" instead (DEC-034: shared with app/ai/context.py).
            upcoming = get_upcoming_appointments(db, business_id, customer_id, limit=1)
            if not upcoming:
                return ToolExecutionResult(
                    False, "No upcoming appointment found to modify.", reason="not_found"
                )
            appointment = upcoming[0]

            if tool_call.name == RESCHEDULE_APPOINTMENT:
                updated = appointment_service.reschedule_appointment(
                    appointment_id=appointment.id,
                    new_starts_at=datetime.fromisoformat(tool_call.arguments["starts_at"]),
                    new_ends_at=datetime.fromisoformat(tool_call.arguments["ends_at"]),
                )
                return ToolExecutionResult(True, "Appointment rescheduled.", updated.id)

            updated = appointment_service.cancel_appointment(appointment_id=appointment.id)
            return ToolExecutionResult(True, "Appointment cancelled.", updated.id)

        return ToolExecutionResult(False, f"Unknown tool '{tool_call.name}'.")
    except CalendarConflictError as exc:
        logger.warning("Tool call %s failed for business %s: %s", tool_call.name, business_id, exc)
        return ToolExecutionResult(False, str(exc), reason="conflict")
    except CalendarAlreadyCancelledError as exc:
        logger.warning("Tool call %s failed for business %s: %s", tool_call.name, business_id, exc)
        return ToolExecutionResult(False, str(exc), reason="already_cancelled")
    except CalendarValidationError as exc:
        logger.warning("Tool call %s failed for business %s: %s", tool_call.name, business_id, exc)
        return ToolExecutionResult(False, str(exc), reason="invalid_request")
    except CalendarError as exc:
        # Any other CalendarError (auth/not-configured/not-connected/
        # provider-unavailable) — unchanged from before this fix; none of
        # these were part of the reported leak (all operational/setup
        # issues, not phrasing a customer would misread as a real answer).
        logger.warning("Tool call %s failed for business %s: %s", tool_call.name, business_id, exc)
        return ToolExecutionResult(False, str(exc))
    except (KeyError, ValueError) as exc:
        logger.warning("Tool call %s had invalid arguments: %s", tool_call.name, exc)
        return ToolExecutionResult(False, "Could not understand the requested date/time.")


def execute_check_availability(db: Session, business_id: uuid.UUID, tool_call: ToolCall) -> str:
    """Read-only — always safe to execute immediately, regardless of Assisted/
    Autonomous mode. Returns a short natural-language note for the system
    prompt (not a ToolExecutionResult — there is nothing here to approve)."""
    try:
        appointment_service = get_appointment_service(db, business_id)
        slots = appointment_service.list_availability(
            starts_at=datetime.fromisoformat(tool_call.arguments["starts_at"]),
            ends_at=datetime.fromisoformat(tool_call.arguments["ends_at"]),
        )
    except CalendarError as exc:
        return f"(Calendar unavailable: {exc}. Do not guess availability — offer to have a human follow up.)"
    except (KeyError, ValueError):
        return "(Could not understand the requested date/time range.)"

    if not slots:
        return "(No free slots in the requested range.)"
    formatted = "; ".join(
        f"{s.starts_at.isoformat()} to {s.ends_at.isoformat()}" for s in slots[:10]
    )
    return f"(Available slots: {formatted})"


# DEC-050: one executor per read-only tool, keyed by name — the same
# generalization as READ_TOOL_NAMES above. app/ai/orchestrator.py's round
# trip looks a proposed read tool up here instead of hardcoding which domain
# it belongs to; a future domain's own read-only lookup (e.g. a CRM status
# check) registers itself the same way, with no orchestrator change needed.
READ_TOOL_EXECUTORS: dict[str, Callable[[Session, uuid.UUID, ToolCall], str]] = {
    CHECK_AVAILABILITY: execute_check_availability,
}
