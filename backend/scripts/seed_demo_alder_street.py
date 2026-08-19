"""Demo seed for "THE ORCHESTRATION" (HIRA Studio launch film) — Alder
Street Dental.

Seeds only the baseline state that must exist *before* recording starts.
Deliberately does NOT pre-create most of the storyboard's conversations —
those are triggered live, on camera, by scripts/demo_playback.py, through
the real inbound-message pipeline, so what's recorded is the genuine
product, not a fixture dressed up to look like it.

What this script seeds, and why:
  - The business itself, Assisted mode by default.
  - Baseline Knowledge Base facts (NOT the one page imported live in
    Beat 09 — that must happen for real, on camera, or the recording
    would be showing a fact HIRA never actually learned).
  - Dana Ostrowski and Nora Fielding: pre-existing appointments, because
    Beats 06/16 and Beat 11 need something already on the calendar to
    reschedule/cancel — you can't film "moving an appointment" without
    one existing first.
  - Renee Castillo: a Lead backdated ~3 weeks, because Beat 14 depends on
    HIRA already knowing about her before she messages again.

Every other persona in the Production Package (Priya, Marcus, Tom, Elena,
Sam, Alicia, Devon, Ibrahim, Layla, Grace, Owen) is intentionally absent
here — scripts/demo_playback.py creates them live.

Same conventions as scripts/seed_demo_workspace.py (business-name-matched
get-or-create, real service functions reused for correctness, full re-sync
on every run rather than additive-only, since this fixture is not meant to
be hand-edited between takes). Run from the backend/ directory:

    .venv/bin/python scripts/seed_demo_alder_street.py
    .venv/bin/python scripts/seed_demo_alder_street.py --mode autonomous
    .venv/bin/python scripts/seed_demo_alder_street.py --mode assisted
"""

from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.knowledge_base import index_entry
from app.calendar.factory import get_appointment_service
from app.db.session import SessionLocal
from app.models import Business, Conversation, Customer, KbEntry, Lead, LeadEvent, Message
from app.services.leads import create_lead

BUSINESS_NAME = "Alder Street Dental"

# (title, content) — baseline facts only. The new-patient-paperwork fact
# from Beat 09 is deliberately absent; it must be imported live for real.
KB_FACTS: list[tuple[str, str]] = [
    (
        "Office hours",
        "Alder Street Dental is open Monday to Friday from 9:00 AM to 5:00 PM, and Saturday "
        "from 9:00 AM to 1:00 PM. We are closed on Sundays.",
    ),
    (
        "Cleanings and exams",
        "A routine cleaning and exam costs 95 USD and takes about 45 minutes.",
    ),
    ("Fillings", "A standard filling costs 140 to 220 USD depending on the tooth and material."),
    ("Teeth whitening", "In-office teeth whitening starts at 250 USD."),
    (
        "X-rays",
        "Routine X-rays are included with your first visit and every other cleaning after that.",
    ),
    (
        "Insurance",
        "We accept Delta Dental, Cigna, Aetna, and MetLife. Bring your insurance card to your "
        "first visit.",
    ),
    (
        "Cancellation policy",
        "Cancellations with at least 24 hours notice are free. Cancelling with less notice may "
        "incur a 25 USD fee.",
    ),
    (
        "Late arrival policy",
        "If you're more than 15 minutes late we may need to reschedule you to protect the rest "
        "of the day's appointments.",
    ),
    ("Parking", "Free parking is available in the lot directly behind the building."),
    (
        "First visit for children",
        "We see children starting at age 3. For anyone younger, we recommend waiting until their "
        "first baby teeth are fully in.",
    ),
    ("Payment methods", "We accept cash, all major credit cards, and HSA/FSA cards."),
    (
        "After-hours emergencies",
        "For a dental emergency outside office hours, call our office line and follow the "
        "recorded instructions for the on-call dentist.",
    ),
]


def _get_or_create_business(db: Session) -> Business:
    existing = db.scalars(select(Business).where(Business.name == BUSINESS_NAME)).first()
    if existing is not None:
        return existing
    business = Business(name=BUSINESS_NAME, mode="assisted", timezone="America/Chicago")
    db.add(business)
    db.flush()
    return business


def _seed_kb(db: Session, business_id: uuid.UUID) -> int:
    """Sync baseline facts to exactly KB_FACTS. Only ever touches manually-
    seeded entries (import_batch_id IS NULL) — a real Beat-09 import always
    carries a batch id (see app/ai/knowledge_base.py::index_entry), so this
    can never delete it, however many times this script is rerun."""
    baseline = db.scalars(
        select(KbEntry).where(KbEntry.business_id == business_id, KbEntry.import_batch_id.is_(None))
    ).all()
    for entry in baseline:
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
    """Clear this customer's conversation/appointment rows so re-running
    rebuilds a clean pre-recording state every time (same reasoning as
    seed_demo_workspace.py's identically-named helper)."""
    for conversation in db.scalars(
        select(Conversation).where(
            Conversation.business_id == business_id, Conversation.customer_id == customer_id
        )
    ).all():
        db.delete(conversation)  # cascades Message
    db.flush()
    from app.models import Appointment

    for appointment in db.scalars(
        select(Appointment).where(
            Appointment.business_id == business_id, Appointment.customer_id == customer_id
        )
    ).all():
        db.delete(appointment)
    db.flush()


def _seed_prior_conversation(
    db: Session, business_id: uuid.UUID, customer: Customer, *, summary: str, hours_ago: int
) -> Conversation:
    """A brief, already-resolved conversation, so Dana/Nora read as existing
    patients rather than appearing on camera with zero history."""
    now = datetime.now(timezone.utc)
    conversation = Conversation(business_id=business_id, customer_id=customer.id, status="active")
    db.add(conversation)
    db.flush()
    created_at = now - timedelta(hours=hours_ago)
    db.add(
        Message(
            conversation_id=conversation.id,
            business_id=business_id,
            direction="inbound",
            body=summary,
            type="text",
            status="received",
            created_at=created_at,
        )
    )
    conversation.last_message_at = created_at
    return conversation


def _seed_dana(db: Session, business: Business) -> None:
    customer = _get_or_create_customer(db, business.id, "Dana Ostrowski", "+15550002003")
    _reset_customer_data(db, business.id, customer.id)
    db.commit()

    _seed_prior_conversation(
        db, business.id, customer, summary="Hi, can I book a cleaning next week?", hours_ago=96
    )
    starts_at = datetime.now(timezone.utc) + timedelta(days=4, hours=3)
    get_appointment_service(db, business.id).book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=45),
        summary="Cleaning — Dana Ostrowski",
    )
    db.commit()


def _seed_nora(db: Session, business: Business) -> None:
    customer = _get_or_create_customer(db, business.id, "Nora Fielding", "+15550002007")
    _reset_customer_data(db, business.id, customer.id)
    db.commit()

    _seed_prior_conversation(
        db,
        business.id,
        customer,
        summary="Can I get a cleaning booked in for next week?",
        hours_ago=72,
    )
    starts_at = datetime.now(timezone.utc) + timedelta(days=3, hours=5)
    get_appointment_service(db, business.id).book_appointment(
        customer_id=customer.id,
        conversation_id=None,
        starts_at=starts_at,
        ends_at=starts_at + timedelta(minutes=45),
        summary="Cleaning — Nora Fielding",
    )
    db.commit()


def _seed_renee_lead(db: Session, business: Business) -> None:
    customer = _get_or_create_customer(db, business.id, "Renee Castillo", "+15550002009")
    for lead in db.scalars(
        select(Lead).where(Lead.business_id == business.id, Lead.customer_id == customer.id)
    ).all():
        db.delete(lead)  # cascades LeadEvent
    db.flush()

    lead = create_lead(
        db,
        business.id,
        customer.id,
        stage="contacted",
        source="WhatsApp inquiry",
        notes="Asked about teeth whitening pricing; hasn't booked yet.",
    )
    backdated_at = datetime.now(timezone.utc) - timedelta(days=21)
    lead.created_at = backdated_at
    lead.updated_at = backdated_at
    for event in db.scalars(select(LeadEvent).where(LeadEvent.lead_id == lead.id)):
        event.created_at = backdated_at
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["assisted", "autonomous"],
        default=None,
        help="Set Business.mode only, without touching any other seeded data.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        business = _get_or_create_business(db)
        db.commit()

        if args.mode is not None:
            business.mode = args.mode
            db.commit()
            print(
                f"Mode set to {args.mode!r} for {business.name!r} (id={business.id}). Nothing else changed."
            )
            return

        kb_count = _seed_kb(db, business.id)
        db.commit()

        _seed_dana(db, business)
        _seed_nora(db, business)
        _seed_renee_lead(db, business)

        print(f"Demo business ready: {business.name!r} (id={business.id}, mode={business.mode!r})")
        print(
            f"Knowledge base: {kb_count} baseline fact(s) (Beat 09's imported page is NOT included)"
        )
        print(
            "Pre-seeded: Dana Ostrowski (appointment), Nora Fielding (appointment), Renee Castillo (lead, backdated 21d)"
        )
        print("Everyone else is created live by scripts/demo_playback.py.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
