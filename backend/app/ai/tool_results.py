"""Shared tool-execution result type, used by both the calendar dispatcher
(app/ai/tools.py, DEC-032) and the CRM dispatcher (app/ai/lead_tools.py,
DEC-033) — split out to avoid a circular import between the two."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass
class ToolExecutionResult:
    success: bool
    message: str
    appointment_id: uuid.UUID | None = None
    lead_id: uuid.UUID | None = None
