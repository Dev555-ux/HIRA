"""Demo workspace seed — a self-contained, richly-populated business for
showing HIRA to beta prospects and prospective customers (Sprint 34).

Unlike scripts/seed_business.py (which wires a business to a *real* WhatsApp
number for live dev testing), this creates a business with no WhatsApp/Google
Calendar connection at all — everything here is explorable purely through
the dashboard (Customers, Leads, Pending Replies, Appointments) and the
Playground, so a beta prospect can see a populated product without HIRA
needing their real credentials first.

Idempotent — matched by business name. Re-running adds only what's missing
(a customer/lead/conversation/appointment already present is left alone),
same convention as seed_business.py/seed_knowledge_base.py. Run from the
backend/ directory:

    .venv/bin/python scripts/seed_demo_workspace.py
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.calendar.providers.mock import MockCalendarProvider
from app.calendar.service import AppointmentService
from app.db.session import SessionLocal
from app.models import Appointment, Business, Conversation, Customer, Message
from app.onboarding.knowledge import seed_facts
from app.services.leads import create_lead, get_lead_for_customer

DEMO_BUSINESS_NAME = "HIRA Demo Workspace"

# (display_name, wa_phone, stage, source, estimated_value, notes, opening line)
DEMO_CUSTOMERS: list[tuple[str, str, str, str, float | None, str, str]] = [
    (
        "Jordan Lee",
        "+15550001001",
        "new",
        "WhatsApp inquiry",
        None,
        "Asked about teeth whitening pricing.",
        "Hi! How much does teeth whitening cost?",
    ),
    (
        "Priya Nair",
        "+15550001002",
        "contacted",
        "Website form",
        400,
        "Interested in a full check-up and cleaning package.",
        "I'd like to book a check-up and cleaning, what's included?",
    ),
    (
        "Sam Torres",
        "+15550001003",
        "qualified",
        "Referral",
        1200,
        "Wants a full smile makeover consultation.",
        "A friend recommended you for a smile makeover — can we set up a consultation?",
    ),
    (
        "Alex Chen",
        "+15550001004",
        "won",
        "WhatsApp inquiry",
        250,
        "Booked and completed a routine cleaning.",
        "Just wanted to say thanks for the cleaning last week, my teeth feel great!",
    ),
    (
        "Morgan Blake",
        "+15550001005",
        "lost",
        "WhatsApp inquiry",
        None,
        "Went with a different clinic closer to home.",
        "Thanks for the info, but I found a clinic closer to home. Appreciate the help!",
    ),
]


def _get_or_create_business(db: Session) -> Business:
    existing = db.scalars(select(Business).where(Business.name == DEMO_BUSINESS_NAME)).first()
    if existing is not None:
        return existing
    business = Business(name=DEMO_BUSINESS_NAME, mode="assisted", timezone="America/New_York")
    db.add(business)
    db.flush()
    return business


def _get_or_create_customer(
    db: Session, business_id: uuid.UUID, display_name: str, wa_phone: str
) -> Customer:
    existing = db.scalars(
        select(Customer).where(Customer.business_id == business_id, Customer.wa_phone == wa_phone)
    ).first()
    if existing is not None:
        return existing
    customer = Customer(business_id=business_id, wa_phone=wa_phone, display_name=display_name)
    db.add(customer)
    db.flush()
    return customer


def _get_or_create_conversation(
    db: Session,
    business_id: uuid.UUID,
    customer: Customer,
    *,
    opening_line: str,
    make_pending: bool,
) -> Conversation:
    existing = db.scalars(
        select(Conversation).where(
            Conversation.business_id == business_id, Conversation.customer_id == customer.id
        )
    ).first()
    if existing is not None:
        return existing

    conversation = Conversation(business_id=business_id, customer_id=customer.id, status="active")
    db.add(conversation)
    db.flush()
    db.add(
        Message(
            conversation_id=conversation.id,
            business_id=business_id,
            direction="inbound",
            body=opening_line,
            type="text",
            status="received",
        )
    )
    db.add(
        Message(
            conversation_id=conversation.id,
            business_id=business_id,
            direction="outbound",
            body="Thanks for reaching out! Let me get back to you on that shortly.",
            type="text",
            status="pending_approval" if make_pending else "sent",
        )
    )
    conversation.last_message_at = datetime.now(timezone.utc)
    return conversation


def main() -> None:
    db = SessionLocal()
    try:
        business = _get_or_create_business(db)
        db.commit()

        inserted = seed_facts(db, business.id)

        won_customer: Customer | None = None
        for i, (name, phone, stage, source, value, notes, opening_line) in enumerate(
            DEMO_CUSTOMERS
        ):
            customer = _get_or_create_customer(db, business.id, name, phone)
            _get_or_create_conversation(
                db, business.id, customer, opening_line=opening_line, make_pending=(i == 0)
            )
            if get_lead_for_customer(db, business.id, customer.id) is None:
                create_lead(
                    db,
                    business.id,
                    customer.id,
                    stage=stage,
                    source=source,
                    estimated_value=value,
                    notes=notes,
                )
            if stage == "won":
                won_customer = customer
        db.commit()

        appointment_created = False
        if won_customer is not None:
            existing_appointment = db.scalars(
                select(Appointment).where(
                    Appointment.business_id == business.id,
                    Appointment.customer_id == won_customer.id,
                )
            ).first()
            if existing_appointment is None:
                starts_at = datetime.now(timezone.utc) + timedelta(days=3, hours=2)
                service = AppointmentService(
                    db, business.id, MockCalendarProvider(), calendar_id="primary"
                )
                service.book_appointment(
                    customer_id=won_customer.id,
                    conversation_id=None,
                    starts_at=starts_at,
                    ends_at=starts_at + timedelta(minutes=30),
                    summary="Follow-up cleaning",
                )
                appointment_created = True

        print(f"Demo workspace ready: business_id={business.id} name={business.name!r}")
        print(f"Knowledge base: {inserted} new fact(s) inserted this run")
        print(f"Customers/leads: {len(DEMO_CUSTOMERS)} across the pipeline (new -> lost)")
        print(f"Appointment: {'created' if appointment_created else 'already existed'}")
        print(
            "Explore via the dashboard (Customers, Leads, Pending Replies, Appointments) and the "
            "Playground — no WhatsApp number or Google Calendar connection required."
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
