"""Shared tool-execution result type, used by both the calendar dispatcher
(app/ai/tools.py, DEC-032) and the CRM dispatcher (app/ai/lead_tools.py,
DEC-033) — split out to avoid a circular import between the two."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class ToolExecutionResult:
    success: bool
    # Written for logs/traces/founder-facing surfaces — never send this to a
    # customer directly on failure (it can read like "Requested slot
    # overlaps an existing appointment" or a governance-policy string, not
    # something HIRA would actually say). See `reason` below and
    # app/ai/tools.py::failure_message_for for the customer-facing text.
    message: str
    appointment_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    # Set only when the tool was executed with commit=False (Section A4):
    # a best-effort compensating action (e.g. delete the external calendar
    # event) the caller must run if its own, later commit fails. None means
    # either nothing needs compensating (e.g. a CRM-only tool) or the tool
    # already committed and handled its own compensation internally.
    on_commit_failure: Callable[[], None] | None = None
    # Machine-readable failure category (None on success, or when nothing
    # here has natural phrasing for it yet) — see
    # app/ai/tools.py::failure_message_for.
    reason: str | None = None
