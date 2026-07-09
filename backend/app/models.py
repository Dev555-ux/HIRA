"""ORM models — the database schema as Python classes.

Each class maps to one table (see documentation/DATABASE.md). Every
business-owned table carries `business_id` for multi-tenant scoping, which is
the foundation of keeping one customer's data isolated from another's.

Notes for learners:
- UUIDs are generated in Python (`default=uuid4`) so rows have an id before
  they hit the database.
- `created_at` / `updated_at` use the database clock (`server_default=now()`).
- Status fields are plain strings for MVP flexibility; allowed values are noted
  in comments. We can tighten these into CHECK constraints / enums later.
- `kb_entries.embedding` uses pgvector. The dimension (1536) is provisional and
  will be set to match the chosen embedding model via a future migration.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    vertical: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "industry" at signup
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    whatsapp_phone_number_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    whatsapp_business_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    mode: Mapped[str] = mapped_column(String(16), default="assisted")  # assisted | autonomous
    # created | live — see ONBOARDING_ARCHITECTURE.md §2.1. Only "created" is set
    # by anything today; "live" is reserved for the future go-live milestone.
    onboarding_status: Mapped[str] = mapped_column(String(32), default="created")
    # not_connected | pending_verification | connected — reserved for the future
    # WhatsApp-connection milestone; nothing sets it beyond the default yet.
    whatsapp_connection_status: Mapped[str] = mapped_column(String(24), default="not_connected")
    website_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    trial_ends_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # {"mon": {"open": "09:00", "close": "17:00"}, ..., "sun": null} — a day's
    # value is null for "closed". NULL (the column, not a day) means "not
    # configured yet" — availability filtering skips the working-hours step
    # rather than blocking all bookings. See DEC-032.
    working_hours: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    clerk_user_id: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(320))
    role: Mapped[str] = mapped_column(String(16), default="owner")  # owner | staff
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("business_id", "wa_phone", name="uq_customer_business_phone"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    wa_phone: Mapped[str] = mapped_column(String(32))
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (
        Index("ix_conversations_business_status_last", "business_id", "status", "last_message_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | escalated | closed
    window_expires_at: Mapped[datetime | None] = mapped_column(nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(nullable=True)
    # Rolling summary of this conversation's messages older than the raw
    # history window fed to the LLM (app/ai/memory.py). NULL = no summary
    # generated yet (conversation hasn't exceeded the window). See DEC-034.
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Watermark: how many of this conversation's oldest messages `summary`
    # already covers. Compared against (total messages - HISTORY_LIMIT) to
    # decide whether the summary needs regenerating. See DEC-034.
    summary_message_count: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    direction: Mapped[str] = mapped_column(String(16))  # inbound | outbound
    wa_message_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    type: Mapped[str] = mapped_column(String(32), default="text")
    status: Mapped[str] = mapped_column(
        String(24), default="received"
    )  # received | pending_approval | sent | failed | rejected | escalated
    ai_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class KbEntry(Base):
    __tablename__ = "kb_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(512))
    content: Mapped[str] = mapped_column(Text)
    # 384 = BAAI/bge-small-en-v1.5 (local embeddings). Changing provider to a
    # different dimension requires a migration. See app/ai/embeddings.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (Index("ix_appointments_business_starts", "business_id", "starts_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    google_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    starts_at: Mapped[datetime] = mapped_column()
    ends_at: Mapped[datetime] = mapped_column()
    status: Mapped[str] = mapped_column(
        String(16), default="booked"
    )  # booked | rescheduled | cancelled
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class Escalation(Base):
    __tablename__ = "escalations"
    __table_args__ = (Index("ix_escalations_business_status", "business_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    reason: Mapped[str] = mapped_column(
        String(32)
    )  # low_confidence | customer_request | external_failure | other
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | resolved
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(nullable=True)


class Lead(Base):
    __tablename__ = "leads"
    __table_args__ = (
        UniqueConstraint("business_id", "customer_id", name="uq_lead_business_customer"),
        Index("ix_leads_business_stage", "business_id", "stage"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    # new | contacted | qualified | proposal_sent | negotiation | won | lost
    # Plain string (no CHECK constraint), matching Message.status/Conversation.status;
    # validated at the API boundary instead (see app/api/leads.py's LeadStage Literal).
    stage: Mapped[str] = mapped_column(String(32), default="new")
    source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    estimated_value: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_follow_up_at: Mapped[datetime | None] = mapped_column(nullable=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class LeadEvent(Base):
    """Append-only history for a Lead — timeline/audit trail only, never mutated.

    Deliberately has no business_id: every query reaches this table by joining
    through Lead.business_id (see app/services/leads.py), since it's always
    accessed in the context of a specific, already-tenant-scoped lead.
    """

    __tablename__ = "lead_events"
    __table_args__ = (Index("ix_lead_events_lead_created", "lead_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"), index=True
    )
    # lead_created | stage_change | notes_updated | follow_up_set | assigned
    type: Mapped[str] = mapped_column(String(32))
    from_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class CalendarCredential(Base):
    __tablename__ = "calendar_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), unique=True
    )
    refresh_token_encrypted: Mapped[str] = mapped_column(Text)
    calendar_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
