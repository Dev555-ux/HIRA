"""Prompt construction for the AI receptionist.

Holds the versioned system prompt and assembles the system prompt + message list
sent to the LLM. Retrieved knowledge is injected into the system prompt so the
model answers *grounded* in the business's knowledge base; conversation history
is passed as prior messages.

Prompt version is recorded so AI behaviour can be traced to a specific prompt
(CLAUDE.md §11). Bump SYSTEM_PROMPT_VERSION when the prompt changes.

v2 (Sprint 29, DEC-032): added booking-tool guidance + optional availability
grounding, now that generate_reply() passes app/ai/tools.py's TOOL_SCHEMAS.

v3 (Sprint 30, DEC-033): added CRM tool-usage guidance now that TOOL_SCHEMAS
also includes app/ai/lead_tools.py's create_lead/update_lead_stage/
set_lead_follow_up.
"""

from __future__ import annotations

from datetime import datetime

from zoneinfo import ZoneInfo

from app.ai.llm.base import ChatMessage
from app.models import Business, KbEntry, Message

SYSTEM_PROMPT_VERSION = "v3"

_BASE_SYSTEM_PROMPT = """\
You are HIRA, a professional AI receptionist replying to a customer on WhatsApp \
on behalf of a business.

Rules:
- Answer ONLY using the information in the "Knowledge base" section below.
- If the answer is not in the knowledge base, do not guess. Say you are not \
sure and that you'll have a team member follow up.
- Be concise, friendly, and professional. Keep replies short — this is WhatsApp.
- Never invent prices, hours, availability, or policies.

Booking appointments:
- Use the check_availability tool before proposing a specific time, unless the \
customer already confirmed one.
- Use book_appointment / reschedule_appointment / cancel_appointment once a \
specific slot is confirmed with the customer. These do not take effect \
immediately — a human reviews the proposed action first.
- Never state or imply that a booking, reschedule, or cancellation is \
confirmed until you are told it succeeded.
- All appointment times you propose must be within the business's current \
date/time and, if working hours are given below, within them.

Tracking leads:
- If a customer shows buying interest (asks about pricing, requests a quote, \
or wants to book a consultation), use create_lead to log them — but only if \
one doesn't already exist for them based on the conversation so far.
- Use update_lead_stage as their interest progresses, and set_lead_follow_up \
if they ask to be contacted again at a specific time.
- These do not take effect immediately — a human reviews the proposed \
action first. Never state or imply a CRM change is confirmed until you are \
told it succeeded.
"""

_NO_KNOWLEDGE = "(No relevant knowledge base entries were found for this question.)"


def _format_knowledge(entries: list[KbEntry]) -> str:
    if not entries:
        return _NO_KNOWLEDGE
    return "\n\n".join(f"- {e.title}: {e.content}" for e in entries)


def _format_scheduling_context(business: Business | None) -> str:
    if business is None:
        return ""
    tz = ZoneInfo(business.timezone)
    now_local = datetime.now(tz)
    lines = [
        f"Current date/time for this business: {now_local.isoformat()} ({business.timezone}).",
    ]
    if business.working_hours:
        hours = ", ".join(
            f"{day}: {value['open']}-{value['close']}" if value else f"{day}: closed"
            for day, value in business.working_hours.items()
        )
        lines.append(f"Working hours: {hours}.")
    return "\n".join(lines)


def build_system_prompt(
    retrieved: list[KbEntry],
    *,
    business: Business | None = None,
    availability_note: str | None = None,
) -> str:
    parts = [_BASE_SYSTEM_PROMPT, f"\nKnowledge base:\n{_format_knowledge(retrieved)}"]
    scheduling_context = _format_scheduling_context(business)
    if scheduling_context:
        parts.append(f"\nScheduling context:\n{scheduling_context}")
    if availability_note:
        parts.append(f"\nAvailability check result:\n{availability_note}")
    return "\n".join(parts)


def build_messages(history: list[Message], user_text: str) -> list[ChatMessage]:
    """Map stored conversation history to chat messages and append the new question.

    inbound -> user, outbound -> assistant. History is assumed oldest-first.
    """
    messages = [
        ChatMessage(role="user" if m.direction == "inbound" else "assistant", content=m.body)
        for m in history
        if m.body
    ]
    messages.append(ChatMessage(role="user", content=user_text))
    return messages
