"""Demo workspace seed — a self-contained, richly-populated business for
showing HIRA to beta prospects and prospective customers (Sprint 34; redesigned
Sprint 43 for pilot/demo readiness — see documentation/DEMO_AND_PILOT_READINESS.md).

Unlike scripts/seed_business.py (which wires a business to a *real* WhatsApp
number for live dev testing), this creates a business with no WhatsApp/Google
Calendar connection at all — everything here is explorable purely through
the dashboard (Dashboard, Inbox, Pending Replies, Customers, Leads,
Appointments, Knowledge Base, Analytics) and the Playground, so a beta
prospect can see a populated product without HIRA needing their real
credentials first.

The dataset is one coherent story — a single fictional dental clinic,
Bright Smile Dental Studio — not five unrelated fixtures. Every customer's
messages, lead stage, and (where applicable) appointment agree with each
other: the pipeline runs new -> contacted -> qualified -> won -> lost, and
only qualified/won customers have a calendar entry, since those are the ones
who actually converted to a booking.

Idempotent in the sense that matters for a fixture business nobody edits by
hand: matched by business name, and every run leaves it in exactly the state
described by KB_FACTS/DEMO_CUSTOMERS below — re-running after editing this
script updates the workspace to match, rather than silently keeping
whatever an older revision of this script created. (Contrast
seed_business.py/seed_knowledge_base.py, which are additive-only — those
seed a real business you might also edit by hand, so they must never
clobber it.) If a business still has the old Sprint 34 name ("HIRA Demo
Workspace"), it is renamed in place rather than duplicated. Run from the
backend/ directory:

    .venv/bin/python scripts/seed_demo_workspace.py

To actually view this workspace in the dashboard under mock auth (no Clerk
configured), see scripts/use_demo_business.py, which repoints the dev mock
user at whichever business you name.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.knowledge_base import index_entry
from app.calendar.providers.mock import MockCalendarProvider
from app.calendar.service import AppointmentService
from app.db.session import SessionLocal
from app.models import Appointment, Business, Conversation, Customer, KbEntry, Lead, Message
from app.services.leads import create_lead, update_lead

OLD_DEMO_BUSINESS_NAME = "HIRA Demo Workspace"
DEMO_BUSINESS_NAME = "Bright Smile Dental Studio"

# (title, content) — Bright Smile Dental Studio's own knowledge base. Distinct
# from app/onboarding/knowledge.py's generic fact set (that one is used for
# scripts/seed_business.py's "HIRA Test Business" and shouldn't be reused here
# — a demo business quoting a different company's name in its own KB would
# break the story for a beta prospect looking at it).
KB_FACTS: list[tuple[str, str]] = [
    (
        "Business name",
        "This business is Bright Smile Dental Studio, a dental clinic offering routine and "
        "cosmetic care.",
    ),
    (
        "Business location",
        "We are located at 118 Harborview Lane, Austin, TX. Free parking is available directly "
        "behind the building.",
    ),
    (
        "Office hours",
        "We are open Monday to Friday from 9:00 AM to 6:00 PM, and Saturday from 10:00 AM to "
        "3:00 PM. We are closed on Sundays.",
    ),
    (
        "Our dentist",
        "Dr. Maya Whitfield is our lead dentist, with over twelve years of experience in general "
        "and cosmetic dentistry.",
    ),
    (
        "Appointment booking",
        "You can book an appointment directly here on WhatsApp — tell us the service you need "
        "and your preferred day and time, and we'll confirm availability.",
    ),
    (
        "Rescheduling and cancellations",
        "To reschedule, message us at least 24 hours before your appointment and we'll move it "
        "free of charge. Cancellations with less than 24 hours notice may incur a 20 percent fee.",
    ),
    (
        "Pricing",
        "A dental consultation costs 60 USD. A standard cleaning costs 90 USD. Teeth whitening "
        "starts at 220 USD. A full smile makeover starts with a free consultation, with final "
        "pricing depending on the treatment plan.",
    ),
    (
        "Payment and insurance",
        "We accept cash, all major cards, and most dental insurance plans. Payment is due at the "
        "time of service unless insurance covers it directly.",
    ),
    (
        "Supported services",
        "Our services include check-ups, cleanings, fillings, teeth whitening, and smile makeover "
        "consultations.",
    ),
]

# Each customer's lead pipeline stage, and the conversation that got them
# there. Messages are (direction, body, status, hours_ago) so the inbox reads
# like a real, ongoing week rather than five identical one-line exchanges
# created in the same second. Only "qualified" and "won" customers convert to
# an actual appointment below — "new"/"contacted" are still mid-conversation,
# and "lost" never booked.
DEMO_CUSTOMERS: list[dict] = [
    {
        "name": "Jordan Lee",
        "phone": "+15550001001",
        "stage": "new",
        "source": "WhatsApp inquiry",
        "value": None,
        "notes": "Asked about teeth whitening pricing; reply is drafted and awaiting approval.",
        "messages": [
            ("inbound", "Hi! Do you take walk-ins?", "received", 26),
            (
                "outbound",
                "We recommend booking ahead, but same-day slots are sometimes available — "
                "want me to check today?",
                "sent",
                25,
            ),
            ("inbound", "Not today — how much does teeth whitening cost?", "received", 2),
            (
                "outbound",
                "Teeth whitening starts at $220 depending on your needs. Want me to check "
                "available times this week?",
                "pending_approval",
                0,
            ),
        ],
    },
    {
        "name": "Priya Nair",
        "phone": "+15550001002",
        "stage": "contacted",
        "source": "Website form",
        "value": 400,
        "notes": "Interested in a full check-up and cleaning package; deciding on timing.",
        "messages": [
            (
                "inbound",
                "I'd like to book a check-up and cleaning, what's included?",
                "received",
                48,
            ),
            (
                "outbound",
                "A check-up is $60 and a standard cleaning is $90 — together that covers a full "
                "exam plus polishing. Would mornings or afternoons work better for you?",
                "sent",
                47,
            ),
            (
                "inbound",
                "Afternoons are better. Let me check my schedule and get back to you.",
                "received",
                20,
            ),
            (
                "outbound",
                "Sounds good — just message whenever you're ready and I'll find a slot that works.",
                "pending_approval",
                19,
            ),
        ],
    },
    {
        "name": "Sam Torres",
        "phone": "+15550001003",
        "stage": "qualified",
        "source": "Referral",
        "value": 1200,
        "notes": "Wants a full smile makeover; consultation booked.",
        "messages": [
            (
                "inbound",
                "A friend recommended you for a smile makeover — can we set up a consultation?",
                "received",
                96,
            ),
            (
                "outbound",
                "Of course! A smile makeover starts with a free consultation with Dr. Whitfield "
                "so she can put together a treatment plan. I can book that for you this week.",
                "sent",
                95,
            ),
            ("inbound", "Perfect, let's do it.", "received", 94),
            ("outbound", "Great — you're booked. See you then!", "sent", 94),
        ],
        "appointment": {"summary": "Smile makeover consultation", "days_from_now": 5},
    },
    {
        "name": "Alex Chen",
        "phone": "+15550001004",
        "stage": "won",
        "source": "WhatsApp inquiry",
        "value": 250,
        "notes": "Completed a routine cleaning; booked a follow-up.",
        "messages": [
            (
                "inbound",
                "Just wanted to say thanks for the cleaning last week, my teeth feel great!",
                "received",
                70,
            ),
            (
                "outbound",
                "So glad to hear it! We'll see you in six months for your next cleaning — "
                "or sooner if anything comes up.",
                "sent",
                69,
            ),
        ],
        "appointment": {"summary": "Follow-up cleaning", "days_from_now": 3},
    },
    {
        "name": "Morgan Blake",
        "phone": "+15550001005",
        "stage": "lost",
        "source": "WhatsApp inquiry",
        "value": None,
        "notes": "Went with a different clinic closer to home.",
        "messages": [
            (
                "inbound",
                "Thanks for the info, but I found a clinic closer to home. Appreciate the help!",
                "received",
                144,
            ),
            (
                "outbound",
                "No problem at all — wishing you the best, and we're here if that ever changes!",
                "sent",
                143,
            ),
        ],
    },
]


def _get_or_create_business(db: Session) -> Business:
    existing = db.scalars(select(Business).where(Business.name == DEMO_BUSINESS_NAME)).first()
    if existing is not None:
        return existing

    old = db.scalars(select(Business).where(Business.name == OLD_DEMO_BUSINESS_NAME)).first()
    if old is not None:
        old.name = DEMO_BUSINESS_NAME
        db.flush()
        return old

    business = Business(name=DEMO_BUSINESS_NAME, mode="assisted", timezone="America/Chicago")
    db.add(business)
    db.flush()
    return business


def _seed_kb(db: Session, business_id: uuid.UUID) -> int:
    """Sync this business's KB to exactly KB_FACTS, replacing whatever was
    there before. This business exists only for this script (no dashboard
    editing expected), so unlike seed_facts()'s pure-additive convention, a
    full replace is used rather than a title-based skip — otherwise a title
    reused from an older KB_FACTS revision (e.g. Sprint 34's generic fact
    set, which this business used to share) would silently keep its old,
    wrong content forever just because the title matched."""
    for entry in db.scalars(select(KbEntry).where(KbEntry.business_id == business_id)).all():
        db.delete(entry)
    db.flush()

    for title, content in KB_FACTS:
        index_entry(db, business_id, title, content)
    return len(KB_FACTS)


def _get_or_create_customer(db: Session, business_id: uuid.UUID, name: str, phone: str) -> Customer:
    existing = db.scalars(
        select(Customer).where(Customer.business_id == business_id, Customer.wa_phone == phone)
    ).first()
    if existing is not None:
        return existing
    customer = Customer(business_id=business_id, wa_phone=phone, display_name=name)
    db.add(customer)
    db.flush()
    return customer


def _reset_customer_data(db: Session, business_id: uuid.UUID, customer_id: uuid.UUID) -> None:
    """Clear this customer's conversation/lead/appointment rows so the rest of
    seeding can rebuild them fresh from DEMO_CUSTOMERS every run (see the
    module docstring on why this business resets rather than skips)."""
    for conversation in db.scalars(
        select(Conversation).where(
            Conversation.business_id == business_id, Conversation.customer_id == customer_id
        )
    ).all():
        db.delete(conversation)  # cascades Message
    for lead in db.scalars(
        select(Lead).where(Lead.business_id == business_id, Lead.customer_id == customer_id)
    ).all():
        db.delete(lead)  # cascades LeadEvent
    for appointment in db.scalars(
        select(Appointment).where(
            Appointment.business_id == business_id, Appointment.customer_id == customer_id
        )
    ).all():
        db.delete(appointment)
    db.flush()


def _create_conversation(
    db: Session,
    business_id: uuid.UUID,
    customer: Customer,
    *,
    messages: list[tuple[str, str, str, int]],
) -> Conversation:
    now = datetime.now(timezone.utc)
    conversation = Conversation(business_id=business_id, customer_id=customer.id, status="active")
    db.add(conversation)
    db.flush()

    last_created_at = now
    for direction, body, status, hours_ago in messages:
        created_at = now - timedelta(hours=hours_ago)
        db.add(
            Message(
                conversation_id=conversation.id,
                business_id=business_id,
                direction=direction,
                body=body,
                type="text",
                status=status,
                created_at=created_at,
            )
        )
        last_created_at = created_at
    conversation.last_message_at = last_created_at
    return conversation


def main() -> None:
    db = SessionLocal()
    try:
        business = _get_or_create_business(db)
        db.commit()

        kb_count = _seed_kb(db, business.id)
        db.commit()

        for entry in DEMO_CUSTOMERS:
            customer = _get_or_create_customer(db, business.id, entry["name"], entry["phone"])
            _reset_customer_data(db, business.id, customer.id)
            db.commit()

            _create_conversation(db, business.id, customer, messages=entry["messages"])

            lead = create_lead(
                db,
                business.id,
                customer.id,
                stage=entry["stage"],
                source=entry["source"],
                estimated_value=entry["value"],
                notes=entry["notes"],
            )
            if entry["stage"] in ("qualified", "won"):
                # A real follow-up date, not just a static note — this is
                # what actually shows up in the lead's activity timeline as a
                # second LeadEvent beyond "lead_created".
                update_lead(
                    db,
                    business.id,
                    lead.id,
                    {"next_follow_up_at": datetime.now(timezone.utc) + timedelta(days=7)},
                )
            db.commit()

            appointment_spec = entry.get("appointment")
            if appointment_spec is not None:
                starts_at = datetime.now(timezone.utc) + timedelta(
                    days=appointment_spec["days_from_now"], hours=2
                )
                service = AppointmentService(
                    db, business.id, MockCalendarProvider(), calendar_id="primary"
                )
                service.book_appointment(
                    customer_id=customer.id,
                    conversation_id=None,
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(minutes=30),
                    summary=appointment_spec["summary"],
                )
                db.commit()

        print(f"Demo workspace ready: business_id={business.id} name={business.name!r}")
        print(f"Knowledge base: synced to {kb_count} fact(s)")
        print(f"Customers/leads: {len(DEMO_CUSTOMERS)} across the pipeline (new -> lost)")
        appointment_count = sum(1 for entry in DEMO_CUSTOMERS if entry.get("appointment"))
        print(f"Appointments: {appointment_count}")
        print(
            "Explore via the dashboard (Dashboard, Inbox, Pending Replies, Customers, Leads, "
            "Appointments, Knowledge Base, Analytics) and the Playground — no WhatsApp number "
            "or Google Calendar connection required. To view it under mock auth, run "
            "scripts/use_demo_business.py."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
