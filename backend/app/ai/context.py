"""Context Builder — assembles everything relevant before every LLM call (DEC-034).

`build_context()` is the single place that gathers business, customer, lead,
upcoming-appointment, knowledge-base, and conversation-memory information for
a turn, so `app/ai/orchestrator.py` stays thin (it just calls this once, then
hands the result to `app/ai/prompts.py::build_system_prompt`). Every piece is
read through an existing service — nothing here talks to a database table
that doesn't already have an owning module:

- Business/Customer: plain `db.get()`, same as every other module already does.
- Lead: `app/services/leads.py::get_lead_for_customer` (DEC-031's service layer).
- Appointments: `app/calendar/service.py::get_upcoming_appointments` (a local
  read of already-booked rows — no CalendarProvider/credentials needed).
- Knowledge base: `app/ai/knowledge_base.py::retrieve_context` (unchanged),
  plus `has_any_entries` (Sprint 55) — a business-level "has this business
  uploaded anything at all" fact, distinct from retrieve_context's per-query
  result, that app/ai/orchestrator.py branches on for Demo Mode.
- Conversation summary: `app/ai/memory.py::get_conversation_summary` (new
  this sprint — the one piece with nowhere to live before DEC-034).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.embeddings import EmbeddingProvider
from app.ai.knowledge_base import has_any_entries, retrieve_context
from app.ai.llm.base import LLMProvider
from app.ai.memory import HISTORY_LIMIT, get_conversation_summary
from app.calendar.service import get_upcoming_appointments
from app.models import Appointment, Business, Conversation, Customer, KbEntry, Lead, Message
from app.services.leads import get_lead_for_customer

RETRIEVAL_K = 5
UPCOMING_APPOINTMENTS_LIMIT = 3


@dataclass
class ConversationContext:
    business: Business
    customer: Customer
    lead: Lead | None
    upcoming_appointments: list[Appointment]
    retrieved_kb: list[KbEntry]
    has_knowledge: bool
    summary: str | None
    history: list[Message]


def load_history(db: Session, conversation_id: uuid.UUID) -> list[Message]:
    """The most recent HISTORY_LIMIT messages, oldest-first (for the prompt)."""
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc())
        .limit(HISTORY_LIMIT)
    ).all()
    return list(reversed(rows))


def build_context(
    db: Session,
    conversation: Conversation,
    user_text: str,
    *,
    llm: LLMProvider | None = None,
    embedding: EmbeddingProvider | None = None,
    k: int = RETRIEVAL_K,
) -> ConversationContext:
    """Gather everything relevant to ground a reply for this turn.

    Read-only except for the conversation summary, which may regenerate and
    persist itself if the raw history window has advanced (see
    app/ai/memory.py) — that write is incidental to context assembly, not a
    reply-generation side effect the caller needs to know about.
    """
    business = db.get(Business, conversation.business_id)
    customer = db.get(Customer, conversation.customer_id)
    lead = get_lead_for_customer(db, conversation.business_id, conversation.customer_id)
    upcoming_appointments = get_upcoming_appointments(
        db, conversation.business_id, conversation.customer_id, limit=UPCOMING_APPOINTMENTS_LIMIT
    )
    retrieved_kb = retrieve_context(
        db, conversation.business_id, user_text, provider=embedding, k=k
    )
    has_knowledge = has_any_entries(db, conversation.business_id)
    summary = get_conversation_summary(db, conversation, llm=llm)
    history = load_history(db, conversation.id)

    return ConversationContext(
        business=business,
        customer=customer,
        lead=lead,
        upcoming_appointments=upcoming_appointments,
        retrieved_kb=retrieved_kb,
        has_knowledge=has_knowledge,
        summary=summary,
        history=history,
    )
