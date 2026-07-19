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

v4 (Sprint 31, DEC-034): build_system_prompt() now takes a single
app/ai/context.py::ConversationContext (assembled by the new Context
Builder) instead of separate retrieved/business params, and injects
customer/lead/upcoming-appointment context plus the conversation summary
from app/ai/memory.py.

Demo Mode (Sprint 55): a second, separate system prompt — build_demo_system_
prompt() — used instead of build_system_prompt() only when
context.has_knowledge is False (app/ai/orchestrator.py branches on it).
Before this, a business with zero Business Knowledge got the *same* prompt
above, which tells the model to ground answers only in the (empty) knowledge
base — the model had nothing to work with and either apologized like
something was broken, or, with tool schemas still on offer and nothing to
schedule, reached for check_availability speculatively even on a bare "Hi"
(app/ai/tools.py's response_to_message_fields already has a fallback for
exactly that misfire). Demo Mode is a fundamentally different prompt for a
fundamentally different situation — introduce HIRA and its capabilities,
never invent business specifics — not a patch on the grounded prompt, and
orchestrator.py omits tool schemas entirely for it so there's nothing left
to misfire toward.
"""

from __future__ import annotations

from datetime import datetime

from app.ai.context import ConversationContext
from app.ai.llm.base import ChatMessage
from app.core.timezones import safe_zoneinfo
from app.models import Business, KbEntry, Lead, Message

SYSTEM_PROMPT_VERSION = "v4"

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

Using customer context:
- If a "Customer context" section is given below, use it to personalize your \
reply and avoid asking for information you already have (e.g. an existing \
lead stage or an upcoming appointment).
- If a "Conversation so far" summary is given, treat it as established fact \
about earlier parts of this conversation — you don't need to re-derive it.
"""

_NO_KNOWLEDGE = "(No relevant knowledge base entries were found for this question.)"


def _format_knowledge(entries: list[KbEntry]) -> str:
    if not entries:
        return _NO_KNOWLEDGE
    return "\n\n".join(f"- {e.title}: {e.content}" for e in entries)


def _format_scheduling_context(business: Business | None) -> str:
    if business is None:
        return ""
    tz = safe_zoneinfo(business.timezone, business_id=business.id)
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


def _format_lead(lead: Lead | None) -> str | None:
    if lead is None:
        return None
    parts = [f"stage: {lead.stage}"]
    if lead.source:
        parts.append(f"source: {lead.source}")
    if lead.estimated_value is not None:
        parts.append(f"estimated value: {lead.estimated_value}")
    if lead.notes:
        parts.append(f"notes: {lead.notes}")
    if lead.next_follow_up_at:
        parts.append(f"next follow-up: {lead.next_follow_up_at.isoformat()}")
    return "Lead — " + ", ".join(parts)


def _format_customer_context(context: ConversationContext) -> str:
    lines = []
    if context.customer.display_name:
        lines.append(f"Name: {context.customer.display_name}")
    lead_line = _format_lead(context.lead)
    if lead_line:
        lines.append(lead_line)
    for appt in context.upcoming_appointments:
        lines.append(
            f"Upcoming appointment: {appt.starts_at.isoformat()} to {appt.ends_at.isoformat()}"
        )
    return "\n".join(lines)


def build_system_prompt(
    context: ConversationContext,
    *,
    availability_note: str | None = None,
) -> str:
    parts = [_BASE_SYSTEM_PROMPT, f"\nKnowledge base:\n{_format_knowledge(context.retrieved_kb)}"]
    scheduling_context = _format_scheduling_context(context.business)
    if scheduling_context:
        parts.append(f"\nScheduling context:\n{scheduling_context}")
    customer_context = _format_customer_context(context)
    if customer_context:
        parts.append(f"\nCustomer context:\n{customer_context}")
    if context.summary:
        parts.append(f"\nConversation so far (summary of earlier messages):\n{context.summary}")
    if availability_note:
        parts.append(f"\nAvailability check result:\n{availability_note}")
    return "\n".join(parts)


DEMO_SYSTEM_PROMPT_VERSION = "demo-v1"

_DEMO_SYSTEM_PROMPT = """\
You are HIRA, an AI Business Employee, chatting with the business owner who's \
trying you out — not a customer.

This workspace hasn't uploaded any Business Knowledge yet, so you don't \
actually know this business's services, pricing, hours, location, or \
policies. Never invent or guess any of it, and never state or imply a \
specific fact about this business you weren't given. If asked something \
business-specific, say plainly and warmly that you haven't learned this \
business yet, and that uploading Business Knowledge is what teaches you — \
never phrase this like an error, a limitation, or an apology.

You already know your own capabilities, and should explain them \
confidently and conversationally when asked, in your own words:
- Once Business Knowledge is uploaded, you'll answer customer questions \
grounded in it — never by guessing.
- You can check calendar availability and propose bookings, reschedules, \
and cancellations (a human reviews proposed actions before they go out).
- You can log and progress leads in the CRM as buying interest comes up.
- You remember the conversation so far, so you won't ask the same thing twice.

Be warm, brief, and genuinely conversational — this is a chat, not a form \
or a support ticket. A greeting deserves a greeting back, not a disclaimer. \
Never open a reply with something like "let me check on that" — you have \
nothing to check yet, so say so plainly instead.
"""

_DEMO_FIRST_TURN_HINT = """\

This is the first message in this conversation. After your answer, close \
with 2-4 short suggestions (your own words, as a short bulleted list) for \
what they could try next — e.g. asking what you can do, whether you can \
schedule meetings, how to teach you, or whether you can create CRM leads. \
Only do this on this first reply; don't repeat suggestions in later turns.
"""


def build_demo_system_prompt(context: ConversationContext) -> str:
    """Demo Mode's system prompt (Sprint 55) — used instead of
    build_system_prompt() whenever context.has_knowledge is False
    (app/ai/orchestrator.py branches on it before calling either). See the
    module docstring for why this is a separate prompt rather than a patch
    on the grounded one.
    """
    parts = [_DEMO_SYSTEM_PROMPT]
    if context.business and context.business.name:
        parts.append(f'\nThis business is called "{context.business.name}".')
    is_first_turn = not any(m.direction == "outbound" for m in context.history)
    if is_first_turn:
        parts.append(_DEMO_FIRST_TURN_HINT)
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
