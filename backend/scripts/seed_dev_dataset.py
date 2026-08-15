"""Large-scale realistic dev dataset — ~50 customers / 120-150 conversations /
300-500 messages / leads / escalations / appointments / execution traces,
spanning the last 90 days, for one fictional dental clinic: Willowbrook
Family Dental.

FOR LOCAL DEVELOPMENT ONLY. Refuses to run unless DATABASE_URL points at
localhost/127.0.0.1 and ENVIRONMENT != production (see _assert_local_db).

Distinct from scripts/seed_demo_workspace.py ("Bright Smile Dental Studio"),
which is a small, hand-curated 5-customer pilot/sales-demo fixture referenced
by name in several existing tests (ops, settings) — that one tells one clean
funnel story on purpose and must not be disturbed. This script targets a
different, larger dataset for a different job: exercising every dashboard
surface (Analytics trends/breakdowns, AI Activity, Calendar, CRM, Ask HIRA)
with volume and variety a 5-row fixture can't provide. Same underlying
conventions (business-name-matched get-or-create, real service functions —
create_lead/update_lead — reused for correctness), scaled up.

Deterministic: every random choice goes through a single `random.Random(SEED)`
instance, so the *shape* of the story (which customer gets which topic, which
stage, which relative offsets) is identical on every run. Absolute timestamps
are anchored to real "now" and expressed as offsets ("38 days ago"), so the
dataset always reads as "the last 90 days" relative to whenever it's run —
matching seed_demo_workspace.py's own hours_ago/days_from_now convention.

Idempotent: matched by business name; every run fully deletes and rebuilds
this business's own data (customers, conversations, messages, leads,
escalations, appointments, execution traces, KB) before regenerating it, so
re-running never accumulates duplicates.

Run from the backend/ directory:

    .venv/bin/python scripts/seed_dev_dataset.py

Then, to actually view it under mock auth (no Clerk configured):

    .venv/bin/python scripts/use_demo_business.py "Willowbrook Family Dental"
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.knowledge_base import index_entry
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import (
    Appointment,
    Business,
    Conversation,
    Customer,
    Escalation,
    ExecutionTrace,
    KbEntry,
    Lead,
    LeadEvent,
    Message,
    User,
)
from app.services.leads import create_lead, update_lead

DEV_BUSINESS_NAME = "Willowbrook Family Dental"
SEED = 84315
WINDOW_DAYS = 90


def _assert_local_db() -> None:
    """Hard stop before touching anything if this doesn't look like a local
    dev database. DATABASE_URL for the real Docker Compose production stack
    points at the `postgres` service name, never localhost (see
    docker-compose.prod.yml) — this is a structural guarantee, not just a
    courtesy check, but it costs nothing to also check explicitly and fail
    loudly rather than rely on that alone."""
    url = settings.database_url
    if "localhost" not in url and "127.0.0.1" not in url:
        raise SystemExit(
            f"Refusing to run: DATABASE_URL does not look like a local database "
            f"({url.split('@')[-1]!r}). This script is for local development only."
        )
    if settings.environment == "production":
        raise SystemExit("Refusing to run with ENVIRONMENT=production.")


# ============================================================================
# Knowledge base
# ============================================================================

KB_FACTS: list[tuple[str, str]] = [
    (
        "Business name",
        "This business is Willowbrook Family Dental, a family dental clinic offering "
        "routine, restorative, and cosmetic care.",
    ),
    (
        "Business location",
        "We are located at 442 Willowbrook Avenue, Suite 3, Denver, CO. There's free "
        "customer parking in the lot behind the building, and we're a 2-minute walk from "
        "the Willowbrook light rail stop.",
    ),
    (
        "Office hours",
        "We are open Monday to Friday from 8:00 AM to 6:00 PM, and Saturday from 9:00 AM "
        "to 2:00 PM. We are closed on Sundays.",
    ),
    (
        "Our dentists",
        "Dr. Elena Castillo (general and restorative dentistry, 15 years' experience) and "
        "Dr. Robert Nguyen (cosmetic dentistry and orthodontics) see patients here.",
    ),
    (
        "Appointment booking",
        "You can book directly here on WhatsApp — tell us the service you need and your "
        "preferred day and time, and we'll confirm availability.",
    ),
    (
        "Rescheduling and cancellations",
        "To reschedule, message us at least 24 hours before your appointment and we'll "
        "move it free of charge. Cancellations with less than 24 hours notice may incur a "
        "25 percent fee.",
    ),
    (
        "Pricing",
        "A new-patient consultation costs 65 USD. A standard cleaning costs 95 USD. A "
        "filling starts at 150 USD depending on size. Teeth whitening starts at 250 USD. "
        "A crown starts at 900 USD. Kids' checkups (under 12) are 50 USD.",
    ),
    (
        "Payment and insurance",
        "We accept cash, all major cards, and most dental insurance plans including Delta "
        "Dental, Cigna, and MetLife. Payment is due at the time of service unless "
        "insurance covers it directly.",
    ),
    (
        "Supported services",
        "Our services include check-ups, cleanings, fillings, root canals, crowns, teeth "
        "whitening, kids' dentistry, and cosmetic consultations.",
    ),
    (
        "Emergency care",
        "For a dental emergency (severe pain, broken tooth, knocked-out tooth) message us "
        "and we'll fit you in the same day whenever possible — call the front desk directly "
        "if it's outside office hours.",
    ),
    (
        "Refunds and billing disputes",
        "Refund and billing dispute requests are reviewed by our front-desk team directly "
        "and aren't handled automatically — a team member will follow up with you.",
    ),
]


# ============================================================================
# Customers
# ============================================================================

CUSTOMER_NAMES: list[str] = [
    "Emma Rodriguez",
    "Liam Patel",
    "Olivia Kim",
    "Noah Thompson",
    "Ava Martinez",
    "Ethan Wright",
    "Sophia Nguyen",
    "Mason Clarke",
    "Isabella Rossi",
    "Lucas Johnson",
    "Mia Anderson",
    "James Okafor",
    "Charlotte Brooks",
    "Benjamin Silva",
    "Amelia Chen",
    "Henry Osei",
    "Harper Douglas",
    "Alexander Reyes",
    "Evelyn Park",
    "Daniel Foster",
    "Abigail Singh",
    "Matthew Bell",
    "Emily Vasquez",
    "Jackson Murphy",
    "Elizabeth Wong",
    "Sebastian Cole",
    "Sofia Ibrahim",
    "Jack Bennett",
    "Avery Morales",
    "Owen Fitzgerald",
    "Ella Cho",
    "Samuel Hayes",
    "Scarlett Diaz",
    "David Mercer",
    "Grace Adeyemi",
    "Joseph Lindqvist",
    "Chloe Fontaine",
    "Wyatt Nakamura",
    "Victoria Alonso",
    "John Whitfield",
    "Riley Osborne",
    "Carter Delacroix",
    "Zoey Abernathy",
    "Luke Castellano",
    "Penelope Marsh",
    "Gabriel Otieno",
    "Layla Hassan",
    "Anthony Pearce",
    "Nora Kowalski",
    "Dylan Sinclair",
]
assert len(CUSTOMER_NAMES) == 50

EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com"]

CUSTOMER_NOTES = [
    "Prefers morning appointments.",
    "Mild dental anxiety — appreciates a slower pace.",
    "Insurance: Delta Dental.",
    "Insurance: Cigna.",
    "Insurance: MetLife.",
    "Referred by a friend.",
    "Prefers text reminders the day before.",
    "Has two kids who also come in for checkups.",
    "Prefers Dr. Castillo.",
    "Prefers Dr. Nguyen.",
    "Works nearby — likes lunch-hour slots.",
]


def _phone(i: int) -> str:
    return f"+1555000{2000 + i}"


def _email(name: str, rng: random.Random) -> str | None:
    if rng.random() > 0.65:
        return None
    local = name.lower().replace(" ", ".")
    return f"{local}@{rng.choice(EMAIL_DOMAINS)}"


# ============================================================================
# Time helpers
# ============================================================================


def _pick_datetime(
    rng: random.Random, now: datetime, *, days_back_max: int = WINDOW_DAYS
) -> datetime:
    """A timestamp somewhere in the last `days_back_max` days, weighted toward
    recent days (busier lately) and weekdays (busy weekdays, quiet weekends —
    the clinic is only open half-days Saturday and closed Sunday)."""
    for _ in range(40):
        days_ago = rng.triangular(0, days_back_max, 0)
        candidate = now - timedelta(days=days_ago)
        if candidate.weekday() >= 5 and rng.random() > 0.3:
            continue
        hour = rng.choice([9, 10, 10, 11, 13, 14, 14, 15, 16, 17, 19, 20])
        return candidate.replace(hour=hour, minute=rng.randint(0, 59), second=0, microsecond=0)
    return now - timedelta(days=rng.uniform(0, days_back_max))


# ============================================================================
# Conversation scenario templates
# ============================================================================
# Each returns a list of "turns": (inbound, outbound_or_None, meta), where
# meta describes the AI-plan shape for that turn — category, action/tool/role
# for ACTION turns, kb retrieval count for KNOWLEDGE turns, escalation for
# turns a human has to take over, and an occasional hard failure. Offsets are
# minutes since the conversation's base timestamp.

SERVICES = [
    "a cleaning",
    "a check-up",
    "a filling",
    "teeth whitening",
    "a crown",
    "a kids' checkup",
]
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def _scenario_pricing(rng, name):
    service = rng.choice(SERVICES)
    price = {
        "a cleaning": "$95",
        "a check-up": "$65",
        "a filling": "starts at $150",
        "teeth whitening": "starts at $250",
        "a crown": "starts at $900",
        "a kids' checkup": "$50",
    }[service]
    return [
        (
            f"Hi, how much does {service} cost?",
            f"{service.capitalize()} {price}. Want me to check available times?",
            {"category": "knowledge", "retrieved_count": rng.randint(1, 2)},
            0,
        ),
    ]


def _scenario_availability(rng, name):
    day = rng.choice(DAYS)
    return [
        (
            f"Do you have anything available {day}?",
            f"Let me check — yes, we have a few openings {day}. Would morning or afternoon work better?",
            {
                "category": "action",
                "action": "calendar_booking",
                "tool": "check_availability",
                "role": "scheduler",
            },
            0,
        ),
        (
            "Afternoon works.",
            "Great, I can pencil you in — just confirm the service and I'll lock it in.",
            {"category": "conversation"},
            rng.randint(2, 20),
        ),
    ]


def _scenario_booking(rng, name):
    service = rng.choice(SERVICES)
    day = rng.choice(DAYS)
    return [
        (
            f"I'd like to book {service} for {day}.",
            f"You're booked for {service} on {day}. See you then!",
            {
                "category": "action",
                "action": "calendar_booking",
                "tool": "book_appointment",
                "role": "scheduler",
            },
            0,
        ),
    ]


def _scenario_rescheduling(rng, name):
    day = rng.choice(DAYS)
    confirmed = rng.random() > 0.3
    turns = [
        (
            f"Can I move my appointment to {day}?",
            "Sure — just to confirm, you'd like to move your existing appointment to "
            f"{day}, is that right?",
            {
                "category": "action",
                "action": "calendar_reschedule",
                "role": "scheduler",
                "clarification_hint": "confirm with the customer that they want to move their "
                "existing appointment to the new date/time before treating it as done",
            },
            0,
        ),
    ]
    if confirmed:
        turns.append(
            (
                "Yes please.",
                f"Done — you're moved to {day}.",
                {
                    "category": "action",
                    "action": "calendar_reschedule",
                    "tool": "reschedule_appointment",
                    "role": "scheduler",
                },
                rng.randint(3, 40),
            )
        )
    return turns


def _scenario_cancellation(rng, name):
    confirmed = rng.random() > 0.25
    turns = [
        (
            "I need to cancel my appointment.",
            "Sorry to hear that — just to confirm, you'd like to cancel it entirely rather "
            "than reschedule?",
            {
                "category": "action",
                "action": "calendar_cancel",
                "role": "scheduler",
                "clarification_hint": "confirm with the customer that they really want to cancel "
                "this appointment before treating it as done",
            },
            0,
        ),
    ]
    if confirmed:
        turns.append(
            (
                "Yes, cancel it.",
                "Done, it's cancelled. Let us know whenever you'd like to rebook.",
                {
                    "category": "action",
                    "action": "calendar_cancel",
                    "tool": "cancel_appointment",
                    "role": "scheduler",
                },
                rng.randint(2, 30),
            )
        )
    return turns


def _scenario_directions(rng, name):
    return [
        (
            "Where are you located exactly?",
            "We're at 442 Willowbrook Avenue, Suite 3 — free parking in the lot behind the "
            "building, and we're right by the Willowbrook light rail stop.",
            {"category": "knowledge", "retrieved_count": 1},
            0,
        ),
    ]


def _scenario_services(rng, name):
    return [
        (
            "What services do you offer?",
            "We do check-ups, cleanings, fillings, root canals, crowns, teeth whitening, "
            "kids' dentistry, and cosmetic consultations. Anything specific I can help with?",
            {"category": "knowledge", "retrieved_count": 2},
            0,
        ),
    ]


def _scenario_followup(rng, name):
    return [
        (
            "Hi, just checking in — is it time for my next cleaning yet?",
            "Good timing — you're about due. Want me to find a slot in the next couple weeks?",
            {
                "category": "action",
                "action": "crm_lead",
                "tool": "set_lead_follow_up",
                "role": "sales_executive",
            },
            0,
        ),
    ]


def _scenario_complaint(rng, name):
    return [
        (
            "I'm not happy — I waited 40 minutes past my appointment time yesterday.",
            None,
            {"category": "conversation", "escalate": True, "escalation_reason": "customer_request"},
            0,
        ),
    ]


def _scenario_refund(rng, name):
    return [
        (
            "I was charged twice for my last visit, I'd like a refund.",
            "I'm sorry about that — refund requests go to our front-desk team directly, "
            "they'll follow up with you shortly.",
            {"category": "conversation", "escalate": True, "escalation_reason": "customer_request"},
            0,
        ),
    ]


def _scenario_faq(rng, name):
    return [
        (
            "Do you accept Cigna insurance?",
            "Yes, we accept Cigna along with Delta Dental and MetLife. Payment is due at "
            "time of service unless insurance covers it directly.",
            {"category": "knowledge", "retrieved_count": 1},
            0,
        ),
    ]


def _scenario_greeting(rng, name):
    return [
        ("Hi there!", "Hi! How can I help you today?", {"category": "conversation"}, 0),
    ]


def _scenario_capability(rng, name):
    return [
        (
            "What can you actually help me with here?",
            "I can help you book, reschedule, or cancel appointments, answer questions about "
            "pricing and services, and pass anything else to our team.",
            {"category": "capability"},
            0,
        ),
    ]


def _scenario_low_confidence(rng, name):
    return [
        (
            "Can you sort out the thing with my brother's appointment from before?",
            None,
            {"category": "conversation", "escalate": True, "escalation_reason": "low_confidence"},
            0,
        ),
    ]


def _scenario_emergency_failed(rng, name):
    return [
        (
            "URGENT — I broke a tooth, can someone see me today??",
            None,
            {
                "category": "action",
                "action": "calendar_booking",
                "tool": "book_appointment",
                "role": "scheduler",
                "fail": True,
            },
            0,
        ),
    ]


SCENARIOS = [
    ("pricing", _scenario_pricing, 3),
    ("availability", _scenario_availability, 2),
    ("booking", _scenario_booking, 3),
    ("rescheduling", _scenario_rescheduling, 2),
    ("cancellation", _scenario_cancellation, 2),
    ("directions", _scenario_directions, 1),
    ("services", _scenario_services, 2),
    ("follow-up", _scenario_followup, 2),
    ("complaint", _scenario_complaint, 1),
    ("refund", _scenario_refund, 1),
    ("faq", _scenario_faq, 2),
    ("greeting", _scenario_greeting, 2),
    ("capability", _scenario_capability, 1),
    ("low_confidence", _scenario_low_confidence, 1),
    ("emergency_failed", _scenario_emergency_failed, 1),
]
_SCENARIO_WEIGHTS = [w for *_, w in SCENARIOS]


# ============================================================================
# DB setup / teardown
# ============================================================================


BUSINESS_TZ = ZoneInfo("America/Denver")

# Matches KB_FACTS's "Office hours" entry exactly — the Calendar page reads
# this column directly, so it must agree with what the KB tells customers.
WORKING_HOURS = {
    "mon": {"open": "08:00", "close": "18:00"},
    "tue": {"open": "08:00", "close": "18:00"},
    "wed": {"open": "08:00", "close": "18:00"},
    "thu": {"open": "08:00", "close": "18:00"},
    "fri": {"open": "08:00", "close": "18:00"},
    "sat": {"open": "09:00", "close": "14:00"},
    "sun": None,
}


def _get_or_create_business(db: Session) -> Business:
    existing = db.scalars(select(Business).where(Business.name == DEV_BUSINESS_NAME)).first()
    if existing is not None:
        # Sync config fields on every run too, not just at creation — so a
        # fix to WORKING_HOURS (or similar) here actually takes effect for
        # businesses created by an earlier revision of this script.
        existing.working_hours = WORKING_HOURS
        existing.onboarding_status = "live"
        existing.whatsapp_connection_status = "connected"
        return existing
    business = Business(
        name=DEV_BUSINESS_NAME,
        vertical="dental_clinic",
        mode="assisted",
        timezone="America/Denver",
        onboarding_status="live",
        whatsapp_connection_status="connected",
        working_hours=WORKING_HOURS,
    )
    db.add(business)
    db.flush()
    return business


def _wipe_business_data(db: Session, business_id: uuid.UUID) -> None:
    """Full rebuild every run — this business exists only for this script.

    Every business-owned FK in this schema is declared `ondelete="CASCADE"`
    at the database level (see app/models.py) with no ORM-level
    `relationship()` involved — so deleting Customer rows alone cascades
    through Conversation -> Message/Escalation/ExecutionTrace and Lead ->
    LeadEvent and Appointment automatically. KbEntry and the seed-created
    staff Users aren't reachable via Customer, so they're deleted
    separately. Staff Users are matched by clerk_user_id prefix, not a
    blanket business_id delete — that must never touch MOCK_CLERK_USER_ID
    ("dev-mock-user"), which scripts/use_demo_business.py owns exclusively
    and may already point at this business.
    """
    for customer in db.scalars(select(Customer).where(Customer.business_id == business_id)).all():
        db.delete(customer)
    for kb in db.scalars(select(KbEntry).where(KbEntry.business_id == business_id)).all():
        db.delete(kb)
    for user in db.scalars(
        select(User).where(User.business_id == business_id, User.clerk_user_id.like("seed-%"))
    ).all():
        db.delete(user)
    db.flush()


def _seed_kb(db: Session, business_id: uuid.UUID) -> int:
    for title, content in KB_FACTS:
        index_entry(db, business_id, title, content)
    return len(KB_FACTS)


def _seed_staff(db: Session, business_id: uuid.UUID) -> list[User]:
    """Two staff users so escalations/leads have a real assignee/resolver to
    point at — distinct clerk_user_ids from MOCK_CLERK_USER_ID
    ("dev-mock-user"), which scripts/use_demo_business.py owns exclusively."""
    users = [
        User(
            business_id=business_id,
            clerk_user_id=f"seed-owner-{business_id}",
            email="elena.castillo@willowbrookdental.example",
            role="owner",
        ),
        User(
            business_id=business_id,
            clerk_user_id=f"seed-frontdesk-{business_id}",
            email="frontdesk@willowbrookdental.example",
            role="staff",
        ),
    ]
    db.add_all(users)
    db.flush()
    return users


# ============================================================================
# Leads
# ============================================================================

# (final_stage, weight) — a believable funnel for a clinic 90 days into real
# use: lots of already-converted patients, a healthy active pipeline, a few
# that didn't convert.
STAGE_WEIGHTS = [
    ("new", 5),
    ("contacted", 8),
    ("qualified", 7),
    ("proposal_sent", 4),
    ("negotiation", 3),
    ("won", 18),
    ("lost", 5),
]
assert sum(w for _, w in STAGE_WEIGHTS) == 50

LEAD_SOURCES = ["WhatsApp inquiry", "Website form", "Referral", "Walk-in", "Google search"]


def _seed_lead(
    db: Session,
    business: Business,
    customer: Customer,
    rng: random.Random,
    now: datetime,
    *,
    final_stage: str,
) -> Lead:
    source = rng.choice(LEAD_SOURCES)
    value = round(rng.uniform(65, 1200), 2) if final_stage not in ("new",) else None
    notes = rng.choice(CUSTOMER_NOTES) if rng.random() > 0.5 else None

    created_days_ago = rng.uniform(5, WINDOW_DAYS)
    lead = create_lead(
        db,
        business.id,
        customer.id,
        stage="new",
        source=source,
        estimated_value=value,
        notes=notes,
    )
    created_at = now - timedelta(days=created_days_ago)
    lead.created_at = created_at
    lead.updated_at = created_at  # nothing has happened to it yet — updated below if that changes
    for ev in db.scalars(select(LeadEvent).where(LeadEvent.lead_id == lead.id)):
        ev.created_at = created_at
    seen_event_ids = {
        ev.id for ev in db.scalars(select(LeadEvent).where(LeadEvent.lead_id == lead.id))
    }

    def _backdate_new_events(at: datetime) -> None:
        """Backdate only the LeadEvent rows update_lead just created (not
        ones an earlier call in this function already stamped) — two
        separate updates (follow-up, then stage change) must each keep
        their own timestamp, not collapse onto the same one."""
        nonlocal seen_event_ids
        rows = list(db.scalars(select(LeadEvent).where(LeadEvent.lead_id == lead.id)))
        for ev in rows:
            if ev.id not in seen_event_ids:
                ev.created_at = at
        seen_event_ids = {ev.id for ev in rows}

    if final_stage not in ("won", "lost"):
        # Every still-active stage (including "new") gets a follow-up date —
        # some overdue (in the past), most upcoming — realistic mix for
        # "which leads are waiting" / "who hasn't replied" queries. Set
        # shortly after creation, not backdated to created_at itself — the
        # follow-up was scheduled a little after the lead came in.
        follow_up_days = rng.uniform(-5, 14)
        lead = update_lead(
            db, business.id, lead.id, {"next_follow_up_at": now + timedelta(days=follow_up_days)}
        )
        follow_up_set_at = created_at + timedelta(hours=rng.uniform(1, 24))
        lead.updated_at = follow_up_set_at
        _backdate_new_events(follow_up_set_at)

    if final_stage != "new":
        lead = update_lead(db, business.id, lead.id, {"stage": final_stage})
        progressed_at = created_at + timedelta(days=rng.uniform(1, max(1.0, created_days_ago - 1)))
        lead.updated_at = progressed_at
        _backdate_new_events(progressed_at)
    return lead


# ============================================================================
# Conversations / messages / escalations / execution traces
# ============================================================================


def _seed_conversation(
    db: Session,
    business: Business,
    customer: Customer,
    rng: random.Random,
    now: datetime,
    *,
    staff: list[User],
) -> tuple[int, int, int, int]:
    """Returns (message_count, escalation_count, trace_count, appointment_hint)."""
    scenario_name, builder, _weight = rng.choices(SCENARIOS, weights=_SCENARIO_WEIGHTS, k=1)[0]
    turns = builder(rng, customer.display_name)

    base = _pick_datetime(rng, now)
    conversation = Conversation(
        business_id=business.id, customer_id=customer.id, status="closed", created_at=base
    )
    db.add(conversation)
    db.flush()

    last_created_at = base
    message_count = 0
    escalation_count = 0
    trace_count = 0
    conversation_escalated = False

    for inbound_text, outbound_text, meta, offset_minutes in turns:
        turn_time = base + timedelta(minutes=offset_minutes)
        inbound = Message(
            conversation_id=conversation.id,
            business_id=business.id,
            direction="inbound",
            body=inbound_text,
            type="text",
            status="received",
            created_at=turn_time,
        )
        db.add(inbound)
        db.flush()
        message_count += 1
        last_created_at = turn_time
        result_ids = [inbound.id]

        category = meta["category"]
        escalate = meta.get("escalate", False)
        fail = meta.get("fail", False)
        reply_time = turn_time + timedelta(
            seconds=rng.randint(20, 240) if not escalate else rng.randint(300, 2700)
        )

        outbound_msg = None
        if fail:
            outbound_msg = Message(
                conversation_id=conversation.id,
                business_id=business.id,
                direction="outbound",
                body="Sorry, I ran into an issue trying to book that — a team member will "
                "follow up shortly.",
                type="text",
                status="failed",
                ai_meta={"failure_reason": "calendar_conflict"},
                created_at=reply_time,
            )
        elif escalate:
            outbound_msg = Message(
                conversation_id=conversation.id,
                business_id=business.id,
                direction="outbound",
                body=outbound_text or "Let me get a team member to help with this.",
                type="text",
                status="escalated",
                created_at=reply_time,
            )
        elif outbound_text is not None:
            ai_meta = (
                {"retrieved_count": meta["retrieved_count"]} if category == "knowledge" else None
            )
            outbound_msg = Message(
                conversation_id=conversation.id,
                business_id=business.id,
                direction="outbound",
                body=outbound_text,
                type="text",
                status="sent",
                ai_meta=ai_meta,
                created_at=reply_time,
            )

        if outbound_msg is not None:
            db.add(outbound_msg)
            db.flush()
            message_count += 1
            last_created_at = reply_time
            result_ids.append(outbound_msg.id)

        # Execution trace for this turn — every turn produces one, matching
        # the real system's write-once-per-turn design.
        steps: list[dict] = []
        proposed_tool_calls: list[dict] = []
        action = meta.get("action")
        if category == "action" and action:
            role = meta.get("role", "scheduler")
            steps = [
                {
                    "domain": "calendar" if action.startswith("calendar") else "crm",
                    "action": action,
                    "role": role,
                    "tools": [],
                }
            ]
            tool = meta.get("tool")
            if tool and not fail:
                proposed_tool_calls = [{"tool_name": tool, "agent_role": role}]
            elif tool and fail:
                proposed_tool_calls = [{"tool_name": tool, "agent_role": role}]

        plan = {
            "category": category,
            "steps": steps,
            "clarification_hint": meta.get("clarification_hint"),
            "active_domain": steps[0]["domain"]
            if steps and meta.get("clarification_hint")
            else None,
            "pending_action": None,
        }
        trace = ExecutionTrace(
            business_id=business.id,
            conversation_id=conversation.id,
            trigger_message_id=inbound.id,
            category=category,
            plan=plan,
            proposed_tool_calls=proposed_tool_calls,
            result_message_ids=[str(mid) for mid in result_ids],
            duration_ms=rng.randint(400, 4200),
            created_at=reply_time,
        )
        db.add(trace)
        trace_count += 1

        if escalate:
            conversation_escalated = True

    conversation.last_message_at = last_created_at

    if conversation_escalated:
        resolved = rng.random() > 0.4
        reason = next(
            (m.get("escalation_reason") for _, _, m, _ in turns if m.get("escalate")), "other"
        )
        escalation = Escalation(
            business_id=business.id,
            conversation_id=conversation.id,
            reason=reason,
            status="resolved" if resolved else "open",
            assigned_to=rng.choice(staff).id if rng.random() > 0.3 else None,
            resolved_by=rng.choice(staff).id if resolved else None,
            created_at=last_created_at,
            resolved_at=last_created_at + timedelta(hours=rng.uniform(0.5, 30))
            if resolved
            else None,
        )
        db.add(escalation)
        escalation_count += 1
        conversation.status = (
            "escalated"
            if not resolved
            else ("closed" if base < now - timedelta(hours=6) else "active")
        )
    else:
        conversation.status = "closed" if base < now - timedelta(hours=6) else "active"

    return (
        message_count,
        escalation_count,
        trace_count,
        scenario_name in ("booking", "availability"),
    )


# ============================================================================
# Appointments
# ============================================================================

APPT_SUMMARIES = [
    "Check-up",
    "Cleaning",
    "Filling",
    "Teeth whitening",
    "Crown fitting",
    "Kids' checkup",
    "Consultation",
    "Follow-up cleaning",
    "Root canal follow-up",
]


def _clamp_to_appointment_slot(rng: random.Random, dt: datetime) -> datetime:
    """Snap to a real bookable slot matching WORKING_HOURS: weekday 8am-6pm,
    Saturday 9am-2pm, never Sunday (rolls forward to Monday) — evaluated in
    the business's own America/Denver time, then converted back to naive
    UTC (every DateTime column in this schema is naive UTC by convention,
    see _normalize_follow_up in app/services/leads.py). Setting the hour
    directly on a UTC-aware value here would be wrong: 9 (UTC) is roughly
    2-3am in Denver, nowhere near business hours. _pick_datetime's own hour
    range is tuned for *message* timing (customers text anytime, including
    evenings) — appointments need this tighter, business-hours-only clamp
    on top of it."""
    local = dt.astimezone(BUSINESS_TZ)
    if local.weekday() == 6:
        local = local + timedelta(days=1)
    hour = rng.randrange(9, 14) if local.weekday() == 5 else rng.randrange(8, 17)
    minute = rng.choice([0, 15, 30, 45])
    local = local.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def _seed_appointments(
    db: Session,
    business: Business,
    customer: Customer,
    rng: random.Random,
    now: datetime,
    count: int,
) -> int:
    created = 0
    for _ in range(count):
        starts_at = _pick_datetime(rng, now, days_back_max=WINDOW_DAYS)
        # A handful land in the near future — upcoming appointments, not just history.
        if rng.random() > 0.85:
            starts_at = now + timedelta(days=rng.uniform(0.5, 10))
        starts_at = _clamp_to_appointment_slot(rng, starts_at)
        duration = rng.choice([30, 30, 45, 60])
        ends_at = starts_at + timedelta(minutes=duration)

        lead_time_days = rng.uniform(1, 14)
        created_at = starts_at - timedelta(days=lead_time_days)
        now_naive = now.replace(
            tzinfo=None
        )  # starts_at is naive-UTC post-clamp; compare like-for-like
        if created_at > now_naive:
            created_at = now_naive - timedelta(hours=rng.uniform(1, 48))

        status = rng.choices(["booked", "cancelled", "rescheduled"], weights=[70, 15, 15], k=1)[0]

        appointment = Appointment(
            business_id=business.id,
            customer_id=customer.id,
            conversation_id=None,
            starts_at=starts_at,
            ends_at=ends_at,
            status=status,
            created_at=created_at,
        )
        db.add(appointment)
        created += 1
    return created


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    _assert_local_db()
    rng = random.Random(SEED)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    try:
        business = _get_or_create_business(db)
        db.commit()

        _wipe_business_data(db, business.id)
        db.commit()

        kb_count = _seed_kb(db, business.id)
        db.commit()

        staff = _seed_staff(db, business.id)
        db.commit()

        customers: list[Customer] = []
        for i, name in enumerate(CUSTOMER_NAMES):
            customer = Customer(
                business_id=business.id,
                wa_phone=_phone(i),
                display_name=name,
                email=_email(name, rng),
                notes=rng.choice(CUSTOMER_NOTES) if rng.random() > 0.6 else None,
            )
            db.add(customer)
            customers.append(customer)
        db.flush()
        db.commit()

        # Leads: one per customer, stage drawn from the funnel-shaped weights,
        # shuffled deterministically so it's not just "first 5 customers are new".
        stage_assignments: list[str] = []
        for stage, weight in STAGE_WEIGHTS:
            stage_assignments.extend([stage] * weight)
        rng.shuffle(stage_assignments)

        stage_by_customer: dict[uuid.UUID, str] = {}
        for customer, stage in zip(customers, stage_assignments, strict=True):
            _seed_lead(db, business, customer, rng, now, final_stage=stage)
            stage_by_customer[customer.id] = stage
        db.commit()

        # Conversations: distributed across customers so returning/converted
        # customers get more history than brand-new inquiries — target ~135.
        TARGET_CONVERSATIONS = 135
        conv_counts: dict[uuid.UUID, int] = {}
        for customer in customers:
            stage = stage_by_customer[customer.id]
            base_n = {
                "won": 3,
                "negotiation": 2,
                "proposal_sent": 2,
                "qualified": 2,
                "contacted": 2,
                "new": 1,
                "lost": 1,
            }[stage]
            conv_counts[customer.id] = base_n

        total_planned = sum(conv_counts.values())
        # Top up with extra conversations on random (weighted toward "won") customers
        # until we hit the target.
        won_customers = [c for c in customers if stage_by_customer[c.id] == "won"]
        while total_planned < TARGET_CONVERSATIONS:
            pick = rng.choice(won_customers or customers)
            conv_counts[pick.id] += 1
            total_planned += 1

        total_messages = 0
        total_escalations = 0
        total_traces = 0
        booking_customers: list[Customer] = []
        for customer in customers:
            for _ in range(conv_counts[customer.id]):
                msgs, escs, traces, was_booking = _seed_conversation(
                    db, business, customer, rng, now, staff=staff
                )
                total_messages += msgs
                total_escalations += escs
                total_traces += traces
                if was_booking:
                    booking_customers.append(customer)
        db.commit()

        # Appointments: qualified+ stages, plus anyone who had a booking-shaped
        # conversation, get 1-3 appointments across the 90-day window.
        appt_eligible_stages = {"qualified", "proposal_sent", "negotiation", "won"}
        total_appointments = 0
        seen: set[uuid.UUID] = set()
        for customer in customers:
            stage = stage_by_customer[customer.id]
            eligible = stage in appt_eligible_stages or customer in booking_customers
            if not eligible or customer.id in seen:
                continue
            seen.add(customer.id)
            count = 2 if stage == "won" and rng.random() > 0.5 else rng.choice([1, 1, 2])
            total_appointments += _seed_appointments(db, business, customer, rng, now, count)
        db.commit()

        stage_counts = {stage: stage_assignments.count(stage) for stage, _ in STAGE_WEIGHTS}

        print(f"Business: {business.name!r} ({business.id})")
        print(f"Knowledge base entries: {kb_count}")
        print(f"Staff users: {len(staff)}")
        print(f"Customers: {len(customers)}")
        print(f"Leads: {len(customers)}  stages={stage_counts}")
        print(f"Conversations: {total_planned}")
        print(f"Messages: {total_messages}")
        print(f"Escalations: {total_escalations}")
        print(f"Execution traces: {total_traces}")
        print(f"Appointments: {total_appointments}")
        print(
            "\nTo view under mock auth:\n"
            '  .venv/bin/python scripts/use_demo_business.py "Willowbrook Family Dental"'
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
