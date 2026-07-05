"""Idempotent update: point the existing business at the current WhatsApp number.

Updates the single business row in place (preserving its id, so seeded KB stays
linked). Keyed on old-or-new phone number id, so re-running is a no-op. Changes
only whatsapp_phone_number_id (+ ensures WABA id and autonomous mode). No schema
change, no duplicate rows. Run from backend/:

    .venv/bin/python scripts/update_business_phone.py
"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Business

OLD_PHONE_NUMBER_ID = "1237957929400631"
NEW_PHONE_NUMBER_ID = "1270860752766508"
WABA_ID = "2511632579311134"


def main() -> None:
    db = SessionLocal()
    try:
        business = db.scalars(
            select(Business).where(
                Business.whatsapp_phone_number_id.in_(
                    [OLD_PHONE_NUMBER_ID, NEW_PHONE_NUMBER_ID]
                )
            )
        ).first()
        if business is None:
            raise SystemExit(
                "No business found with the old or new phone number id. "
                "Run scripts/seed_business.py first."
            )

        business.whatsapp_phone_number_id = NEW_PHONE_NUMBER_ID
        business.whatsapp_business_account_id = WABA_ID
        business.mode = "autonomous"
        db.commit()
        db.refresh(business)
        print(
            f"updated: id={business.id} "
            f"whatsapp_phone_number_id={business.whatsapp_phone_number_id} "
            f"whatsapp_business_account_id={business.whatsapp_business_account_id} "
            f"mode={business.mode}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
