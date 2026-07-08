"""Bootstrap Service — top-level entry points for dev/ops onboarding scripts.

Phase 1 (business identity): `seed_business` and `rotate_whatsapp_number`
provision a Business row and connect it to a WhatsApp phone_number_id.
Phase 2 (knowledge): `seed_knowledge_base` seeds a business's starter
knowledge base.

Each function owns its own DB session (via `SessionLocal`) so the thin CLI
scripts in `scripts/` don't need to manage SQLAlchemy directly. Business
logic itself lives in `app.onboarding.{business,whatsapp,knowledge}`; this
module only wires those together and handles session lifecycle.
"""

from __future__ import annotations

from app.db.session import SessionLocal
from app.models import Business
from app.onboarding import business as business_ops
from app.onboarding import knowledge as knowledge_ops
from app.onboarding import verification
from app.onboarding import whatsapp as whatsapp_ops


def seed_business(
    *,
    name: str,
    phone_number_id: str,
    whatsapp_business_account_id: str,
    mode: str = "autonomous",
) -> tuple[Business, str]:
    """Phase 1: create or update the business wired to `phone_number_id`."""
    db = SessionLocal()
    try:
        return business_ops.create_or_update_business(
            db,
            name=name,
            phone_number_id=phone_number_id,
            whatsapp_business_account_id=whatsapp_business_account_id,
            mode=mode,
        )
    finally:
        db.close()


def rotate_whatsapp_number(
    *,
    old_phone_number_id: str,
    new_phone_number_id: str,
    whatsapp_business_account_id: str,
    mode: str = "autonomous",
) -> Business:
    """Phase 1: repoint an existing business at a new phone_number_id."""
    db = SessionLocal()
    try:
        return whatsapp_ops.connect_phone_number(
            db,
            old_phone_number_id=old_phone_number_id,
            new_phone_number_id=new_phone_number_id,
            whatsapp_business_account_id=whatsapp_business_account_id,
            mode=mode,
        )
    finally:
        db.close()


def seed_knowledge_base(*, phone_number_id: str | None = None) -> tuple[Business, int, int]:
    """Phase 2: seed starter knowledge facts for a business.

    Resolves the target business (the sole business, or by `phone_number_id`
    when there are several), inserts any missing facts, and returns
    (business, inserted_count, total_count).
    """
    db = SessionLocal()
    try:
        business = verification.resolve_sole_or_by_phone_number_id(db, phone_number_id)
        inserted = knowledge_ops.seed_facts(db, business.id)
        total = knowledge_ops.count_kb_entries(db, business.id)
        return business, inserted, total
    finally:
        db.close()
