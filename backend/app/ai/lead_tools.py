"""CRM tool definitions and dispatcher — the AI's lead-pipeline actions (DEC-033).

Mirrors app/ai/tools.py's shape for the calendar tools, but kept in its own
module since CRM and calendar are different domains even though both plug
into the same Message/ToolCall/pending-approval plumbing. `TOOL_SCHEMAS` in
app/ai/tools.py includes LEAD_TOOL_SCHEMAS, and its preview_tool_call/
execute_tool_call delegate here for any tool name in LEAD_TOOL_NAMES — no
other call site needs to know CRM tools exist separately from calendar ones.

Every write goes through app/services/leads.py (create_lead/update_lead),
never a new data-access path — same one-lead-per-customer schema as DEC-031.
All three tools are approval-gated behind the existing Pending Approvals
mechanism in Assisted Mode, executed immediately only in Autonomous Mode,
exactly like the calendar tools (DEC-033).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.llm.base import ToolCall, ToolSchema
from app.ai.tool_results import ToolExecutionResult
from app.models import Lead
from app.services.leads import (
    CustomerNotFoundError,
    InvalidAssigneeError,
    LeadAlreadyExistsError,
    LeadNotFoundError,
    create_lead,
    update_lead,
)

logger = logging.getLogger(__name__)

CREATE_LEAD = "create_lead"
UPDATE_LEAD_STAGE = "update_lead_stage"
SET_LEAD_FOLLOW_UP = "set_lead_follow_up"

LEAD_TOOL_NAMES = {CREATE_LEAD, UPDATE_LEAD_STAGE, SET_LEAD_FOLLOW_UP}

# Matches the Literal stage set the API layer validates against (DEC-031).
_STAGES = ["new", "contacted", "qualified", "proposal_sent", "negotiation", "won", "lost"]

LEAD_TOOL_SCHEMAS = [
    ToolSchema(
        name=CREATE_LEAD,
        description=(
            "Log this customer as a sales lead when they show buying interest "
            "(e.g. asking about pricing, requesting a quote, or wanting to book a "
            "consultation). Only call this if a lead doesn't already exist for them — "
            "check the conversation so far before calling it a second time. This does "
            "not take effect immediately — a human reviews it first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "How this lead came in, e.g. 'WhatsApp inquiry'",
                },
                "notes": {
                    "type": "string",
                    "description": "Brief context about what the customer is interested in",
                },
            },
            "required": [],
        },
    ),
    ToolSchema(
        name=UPDATE_LEAD_STAGE,
        description=(
            "Move this customer's existing lead to a new pipeline stage as the "
            "conversation progresses. Valid stages: " + ", ".join(_STAGES) + ". This does "
            "not take effect immediately — a human reviews it first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "stage": {
                    "type": "string",
                    "enum": _STAGES,
                    "description": "The new pipeline stage",
                },
            },
            "required": ["stage"],
        },
    ),
    ToolSchema(
        name=SET_LEAD_FOLLOW_UP,
        description=(
            "Schedule a follow-up date/time for this customer's existing lead, e.g. "
            "when they ask to be contacted again later. This does not take effect "
            "immediately — a human reviews it first."
        ),
        parameters={
            "type": "object",
            "properties": {
                "follow_up_at": {
                    "type": "string",
                    "description": "ISO 8601 datetime for the follow-up",
                },
            },
            "required": ["follow_up_at"],
        },
    ),
]


def preview_lead_tool_call(tool_call: ToolCall) -> str:
    """Human-readable, editable preview shown in the Pending queue before approval."""
    args = tool_call.arguments
    if tool_call.name == CREATE_LEAD:
        source = args.get("source")
        return "Log as a new lead" + (f" (source: {source})" if source else "")
    if tool_call.name == UPDATE_LEAD_STAGE:
        return f"Move lead to stage '{args.get('stage', '?')}'"
    if tool_call.name == SET_LEAD_FOLLOW_UP:
        return f"Set a follow-up for {args.get('follow_up_at', '?')}"
    return f"{tool_call.name}({args})"


def _get_lead_for_customer(
    db: Session, business_id: uuid.UUID, customer_id: uuid.UUID
) -> Lead | None:
    return db.scalars(
        select(Lead).where(Lead.business_id == business_id, Lead.customer_id == customer_id)
    ).first()


def execute_lead_tool_call(
    db: Session,
    business_id: uuid.UUID,
    tool_call: ToolCall,
    *,
    customer_id: uuid.UUID,
) -> ToolExecutionResult:
    """Executes a CRM write tool (create/update-stage/set-follow-up) for real.

    Called only from app/ai/tools.py's execute_tool_call, after the calling
    action has already been approved (or, in Autonomous Mode, immediately).
    """
    if tool_call.name not in LEAD_TOOL_NAMES:
        return ToolExecutionResult(False, f"Unknown tool '{tool_call.name}'.")

    try:
        if tool_call.name == CREATE_LEAD:
            lead = create_lead(
                db,
                business_id,
                customer_id,
                source=tool_call.arguments.get("source"),
                notes=tool_call.arguments.get("notes"),
            )
            return ToolExecutionResult(True, "Lead logged.", lead_id=lead.id)

        lead = _get_lead_for_customer(db, business_id, customer_id)
        if lead is None:
            return ToolExecutionResult(False, "No lead found for this customer yet.")

        if tool_call.name == UPDATE_LEAD_STAGE:
            stage = tool_call.arguments["stage"]
            if stage not in _STAGES:
                return ToolExecutionResult(False, f"'{stage}' is not a valid lead stage.")
            updated = update_lead(db, business_id, lead.id, {"stage": stage})
            return ToolExecutionResult(True, f"Lead moved to '{stage}'.", lead_id=updated.id)

        follow_up_at = datetime.fromisoformat(tool_call.arguments["follow_up_at"])
        updated = update_lead(db, business_id, lead.id, {"next_follow_up_at": follow_up_at})
        return ToolExecutionResult(True, "Follow-up scheduled.", lead_id=updated.id)
    except LeadAlreadyExistsError:
        existing = _get_lead_for_customer(db, business_id, customer_id)
        return ToolExecutionResult(
            False,
            "A lead already exists for this customer.",
            lead_id=existing.id if existing else None,
        )
    except (CustomerNotFoundError, InvalidAssigneeError, LeadNotFoundError) as exc:
        logger.warning("Tool call %s failed for business %s: %s", tool_call.name, business_id, exc)
        return ToolExecutionResult(False, str(exc))
    except (KeyError, ValueError) as exc:
        logger.warning("Tool call %s had invalid arguments: %s", tool_call.name, exc)
        return ToolExecutionResult(False, "Could not understand the requested date/time.")
