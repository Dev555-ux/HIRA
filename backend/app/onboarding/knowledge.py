"""Knowledge-base seeding for the bootstrap service (Phase 2).

`seed_facts` inserts a fixed set of demo facts for a business, skipping any
whose title already exists (idempotent). Business resolution is handled by
`app.onboarding.verification`, not here — this module only touches KB rows,
via the existing `index_entry` (chunk + embed + store) so retrieval,
embeddings, and prompts are unaffected.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.knowledge_base import index_entry
from app.models import KbEntry

FACTS: list[tuple[str, str]] = [
    ("Business name", "This business is HIRA Test Business, a dental and wellness clinic."),
    (
        "Business description",
        "HIRA Test Business is a dental and wellness clinic offering routine check-ups, "
        "cleanings, and cosmetic dental treatments. Our AI receptionist answers questions "
        "and books appointments on WhatsApp.",
    ),
    (
        "Office hours",
        "We are open Monday to Friday from 9:00 AM to 6:00 PM, and Saturday from 10:00 AM "
        "to 2:00 PM. We are closed on Sundays and public holidays.",
    ),
    (
        "Appointment booking",
        "You can book an appointment directly here on WhatsApp. Tell us the service you need "
        "and your preferred day and time, and we will confirm availability. Appointments are "
        "recommended, but same-day slots are sometimes available.",
    ),
    (
        "Rescheduling appointments",
        "To reschedule, message us at least 24 hours before your appointment with your name "
        "and preferred new time, and we will move your booking free of charge.",
    ),
    (
        "Cancellation policy",
        "Appointments cancelled at least 24 hours in advance are free. Cancellations with less "
        "than 24 hours notice, or missed appointments, may incur a fee of 20 percent of the "
        "service price.",
    ),
    (
        "Pricing policy",
        "A dental consultation costs 50 USD. A standard cleaning costs 80 USD. Teeth whitening "
        "starts at 200 USD. Final pricing is confirmed after the dentist assesses your needs.",
    ),
    (
        "Refund policy",
        "Prepaid services that have not been used can be refunded within 14 days of payment. "
        "Completed treatments are non-refundable. Refunds are processed to the original payment "
        "method within 7 business days.",
    ),
    (
        "Payment methods",
        "We accept cash, all major credit and debit cards, and mobile payments. Payment is due "
        "at the time of service unless otherwise arranged.",
    ),
    (
        "Insurance",
        "We accept most major dental insurance plans. Please bring your insurance details to "
        "your visit, and we will help you check your coverage.",
    ),
    (
        "Supported services",
        "Our services include dental check-ups, cleanings, fillings, tooth extractions, teeth "
        "whitening, and cosmetic consultations.",
    ),
    (
        "Business location",
        "We are located at 42 Wellness Avenue, Downtown. Parking is free for patients behind the "
        "building, and we are a 5 minute walk from the Central metro station.",
    ),
    (
        "Contact information",
        "You can reach us on WhatsApp at this number, by phone at +1-555-010-2020, or by email "
        "at hello@hiratestclinic.example.",
    ),
    (
        "Response times",
        "Our AI receptionist replies instantly, 24 hours a day. Requests that need a human team "
        "member are answered during office hours, usually within a few hours.",
    ),
    (
        "Languages supported",
        "We support English and Spanish. Let us know your preferred language and we will assist "
        "you in it.",
    ),
    (
        "Emergency contact policy",
        "For a dental emergency during office hours, message us and we will prioritise you. "
        "Outside office hours, for a severe emergency please call our on-call line at "
        "+1-555-010-9111 or go to the nearest emergency room.",
    ),
    (
        "Privacy policy summary",
        "We keep your personal and health information confidential and use it only to provide "
        "care and manage your appointments. We never sell your data. You can request a copy or "
        "deletion of your data at any time.",
    ),
    (
        "General FAQ",
        "New patients are welcome and walk-ins are accepted when slots are free. First visits "
        "usually take about 45 minutes. Please arrive 10 minutes early to complete registration.",
    ),
]


def seed_facts(db: Session, business_id: uuid.UUID) -> int:
    """Insert any FACTS not already present (matched by title) for a business.

    Returns the number of facts inserted.
    """
    inserted = 0
    for title, content in FACTS:
        already = db.scalars(
            select(KbEntry).where(KbEntry.business_id == business_id, KbEntry.title == title)
        ).first()
        if already is not None:
            continue
        index_entry(db, business_id, title, content)
        inserted += 1
    db.commit()
    return inserted


def count_kb_entries(db: Session, business_id: uuid.UUID) -> int:
    """Total KB rows for a business."""
    return len(db.scalars(select(KbEntry).where(KbEntry.business_id == business_id)).all())
