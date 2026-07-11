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
    message: str
    appointment_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
    # Set only when the tool was executed with commit=False (Section A4):
    # a best-effort compensating action (e.g. delete the external calendar
    # event) the caller must run if its own, later commit fails. None means
    # either nothing needs compensating (e.g. a CRM-only tool) or the tool
    # already committed and handled its own compensation internally.
    on_commit_failure: Callable[[], None] | None = None
