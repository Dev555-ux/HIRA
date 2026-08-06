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
from sqlalchemy import ForeignKey, Index, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.jobs.models import JobOutbox, JobStatus  # noqa: F401  — register on Base.metadata


class Business(Base):
    __tablename__ = "businesses"
    __table_args__ = (
        # Partial (not full) unique: whatsapp_phone_number_id is NULL for every
        # business that hasn't connected WhatsApp yet, and those NULLs must
        # coexist. Only actually-connected numbers need to be distinct — two
        # businesses sharing one Meta phone_number_id would have the webhook
        # route that number's inbound messages to whichever business connected
        # it last (app/webhooks/whatsapp.py looks businesses up by this field).
        Index(
            "uq_businesses_whatsapp_phone_number_id",
            "whatsapp_phone_number_id",
            unique=True,
            postgresql_where=text("whatsapp_phone_number_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    vertical: Mapped[str | None] = mapped_column(String(100), nullable=True)  # "industry" at signup
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    contact_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    whatsapp_phone_number_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    whatsapp_business_account_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # The actual dialable number (e.g. "+1 555 123 4567"), distinct from
    # whatsapp_phone_number_id (a Meta-internal identifier, not a phone
    # number). Meta returns this from the same verify_whatsapp_credentials()
    # call already made at connect time — captured here (Sprint 72) so the
    # wizard's verify step can tell a business owner which number to
    # actually text, instead of only referencing "your connected number."
    whatsapp_display_phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
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
        # NULL wa_phone is allowed (Postgres treats NULLs as distinct under a
        # UNIQUE constraint) — a manually-added customer (Sprint 37) may not
        # have a WhatsApp number yet; the constraint still fully protects
        # every customer that does have one.
        UniqueConstraint("business_id", "wa_phone", name="uq_customer_business_phone"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    wa_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Manual-entry fields (Sprint 37) — never populated by the WhatsApp
    # webhook, only by POST/PATCH /api/v1/customers.
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Sprint 38 — set by manual lead creation (POST /api/v1/leads) or
    # POST/PATCH /api/v1/customers; never by the WhatsApp webhook.
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
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
    __table_args__ = (
        Index("ix_messages_conversation_created", "conversation_id", "created_at"),
        # Critical audit fix #2, Part D: backs
        # app/services/replies.py::recover_stale_sending_messages' sweep for
        # Messages stuck in "sending" past a timeout — partial, same
        # reasoning as app/jobs/models.py's ix_job_outbox_zombie, since
        # "sending" is always a tiny, transient slice of a table that
        # otherwise grows unboundedly with every inbound/outbound message.
        Index(
            "ix_messages_sending_updated",
            "status",
            "updated_at",
            postgresql_where=text("status = 'sending'"),
        ),
    )

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
    )  # received | pending_approval | sending | sent | failed | rejected | escalated
    ai_meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    # Critical audit fix #2, Part D: the only way to tell how long a Message
    # has been sitting in its *current* status (specifically "sending" —
    # see recover_stale_sending_messages above) — created_at reflects when
    # the row was first written (e.g. when an Assisted-Mode draft entered
    # the pending-approval queue), which can be arbitrarily long before a
    # human later approves it and it briefly moves through "sending".
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


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
    # Draft -> Review -> Approve -> Publish (Sprint 69, DEC-039). Manually
    # typed facts are published immediately (the owner already reviewed their
    # own text by definition); only website import creates "draft" rows.
    # Retrieval (app/ai/knowledge_base.py) filters to "published" only — a
    # draft must never ground a live customer-facing answer.
    status: Mapped[str] = mapped_column(String(20), default="published", server_default="published")
    # Shared by every chunk from one website import, so a whole scrape can be
    # reviewed/approved together. NULL for manually-typed entries.
    import_batch_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True, index=True)
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
    )  # low_confidence | customer_request | external_failure | automation_failed | other
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | resolved
    # Self-claim, not assign-to-others (Sprint 69) — there's no team roster/
    # picker UI, so a team member claims a queue item for themself rather
    # than assigning a colleague's escalation for them.
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
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


class WhatsAppCredential(Base):
    """A business's own Meta System User token + app secret (Sprint 69,
    self-serve "guided-manual v1" WhatsApp connection) — mirrors
    CalendarCredential's shape exactly (one row per business, secrets
    encrypted at rest with the same Fernet key). `Business.
    whatsapp_phone_number_id`/`whatsapp_business_account_id` are not
    secrets and stay where they already were; only the two actual
    credentials live here."""

    __tablename__ = "whatsapp_credentials"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), unique=True
    )
    access_token_encrypted: Mapped[str] = mapped_column(Text)
    app_secret_encrypted: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class ExecutionTrace(Base):
    """One row per customer turn's app/ai/plan.py::ExecutionPlan (Sprint 76)
    — a dedicated table, not another ai_meta key, because a trace is
    turn-level (one turn can produce up to two Message rows, per Sprint 74's
    MAX_TOOL_CALLS_PER_TURN) and Objectives B/C/D all want to query/compare/
    aggregate whole plans, including domains the plan *skipped*, which no
    single Message row owns.

    Write-once, never retroactively updated: `result_message_ids` records
    which Message row(s) this turn produced, and "execution outcome" for
    Assisted-Mode actions (approved/rejected/executed later, asynchronously,
    by app/services/replies.py) is derived at *read* time by joining to
    those Messages' current status — see app/services/execution_traces.py.
    This keeps replies.py completely untouched by this sprint.
    """

    __tablename__ = "execution_traces"
    __table_args__ = (
        Index("ix_execution_traces_business_created", "business_id", "created_at"),
        # Critical audit fix #3, Part C: backs
        # app/ai/processing.py::generate_reply_into_session's idempotency
        # check ("has this trigger already been processed?") — without it,
        # that check would be a full scan of a table that grows with every
        # customer turn forever. Partial + unique, not just an index: NULL
        # coexists many times over (same reasoning as Business.
        # whatsapp_phone_number_id / Message.wa_message_id elsewhere in this
        # file), but a *real* trigger_message_id can back at most one
        # committed trace — this is the actual, DB-enforced backstop against
        # ever durably recording two replies for the same inbound message,
        # not just an optimization.
        Index(
            "uq_execution_traces_trigger_message_id",
            "trigger_message_id",
            unique=True,
            postgresql_where=text("trigger_message_id IS NOT NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    # The inbound Message that triggered this turn. Nullable + SET NULL:
    # a trace should outlive the message it came from being touched by
    # anything else this schema might do to Message rows later.
    trigger_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    # app/ai/intent.py::ConversationCategory value — conversation | capability
    # | knowledge | action.
    category: Mapped[str] = mapped_column(String(16))
    # {"category", "steps": [{"domain", "action", "role", "tools": [...]}],
    # "clarification_hint": str | null} — the ExecutionPlan actually built,
    # including why planning stopped early if it did (see
    # app/services/execution_traces.py::_serialize_plan and
    # app/ai/plan.py::ExecutionPlan).
    plan: Mapped[dict] = mapped_column(JSONB)
    # [{"tool_name", "agent_role"}, ...] — what the model actually proposed
    # from the plan's offered tools, capped at MAX_TOOL_CALLS_PER_TURN. Can
    # be fewer than `plan.steps` (the model isn't required to use every
    # tool it's offered), informing "abandoned" plans (Objective E).
    proposed_tool_calls: Mapped[list] = mapped_column(JSONB)
    # The outbound Message row(s) this turn produced, in order — joined at
    # read time for current status/tool_result, never duplicated here.
    result_message_ids: Mapped[list] = mapped_column(JSONB)
    duration_ms: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
