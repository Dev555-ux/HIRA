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
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.ai.lead_tools import (
    LEAD_TOOL_NAMES,
    LEAD_TOOL_SCHEMAS,
    execute_lead_tool_call,
    preview_lead_tool_call,
)
from app.ai.llm.base import LLMResponse, ToolCall, ToolSchema
from app.ai.tool_results import ToolExecutionResult
from app.calendar.factory import get_appointment_service
from app.calendar.providers.base import CalendarError
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


def response_to_message_fields(response: LLMResponse) -> tuple[str, str, dict]:
    """(type, body, extra_ai_meta) for storing an LLMResponse as a Message.

    Shared by app/ai/processing.py (initial generation) and
    app/services/replies.py (regenerate), so a regenerated draft can flip
    between a plain-text reply and a proposed tool call exactly like the
    first generation did — no separate code path for each.
    """
    if response.tool_calls:
        tool_call = response.tool_calls[0]  # MVP: one proposed action per turn
        if tool_call.name == CHECK_AVAILABILITY:
            # check_availability is read-only and meant to be resolved
            # entirely inside generate_reply()'s bounded round-trip
            # (app/ai/orchestrator.py). Reaching here means the model asked
            # again after that round-trip (observed live with Groq/Llama on
            # an unconnected calendar) — there's nothing meaningful to
            # approve for a read-only lookup, so this falls back to plain
            # text rather than surfacing a confusing "pending" availability
            # check that approve_and_send couldn't execute anyway.
            return "text", response.text or "Let me check on that and get back to you.", {}
        return (
            "tool_call",
            preview_tool_call(tool_call),
            {"tool_name": tool_call.name, "tool_arguments": tool_call.arguments},
        )
    return "text", response.text, {}


def execute_tool_call(
    db: Session,
    business_id: uuid.UUID,
    tool_call: ToolCall,
    *,
    customer_id: uuid.UUID,
    conversation_id: uuid.UUID | None,
    commit: bool = True,
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
    """
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
                return ToolExecutionResult(False, "No upcoming appointment found to modify.")
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
    except CalendarError as exc:
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
