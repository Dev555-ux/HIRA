"""Additive seed: one autonomous business wired to the live WhatsApp number.

Idempotent — if a business with this whatsapp_phone_number_id already exists it is
updated to autonomous mode rather than duplicated. Uses only existing model
fields; changes no schema. Run from the backend/ directory:

    .venv/bin/python scripts/seed_business.py
"""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Business

PHONE_NUMBER_ID = "1237957929400631"
WABA_ID = "2511632579311134"
BUSINESS_NAME = "HIRA Test Business"


def main() -> None:
    db = SessionLocal()
    try:
        business = db.scalars(
            select(Business).where(Business.whatsapp_phone_number_id == PHONE_NUMBER_ID)
        ).first()
        if business is None:
            business = Business(
                name=BUSINESS_NAME,
                whatsapp_phone_number_id=PHONE_NUMBER_ID,
                whatsapp_business_account_id=WABA_ID,
                mode="autonomous",
            )
            db.add(business)
            action = "created"
        else:
            business.mode = "autonomous"
            business.whatsapp_business_account_id = WABA_ID
            action = "updated"
        db.commit()
        db.refresh(business)
        print(
            f"{action}: id={business.id} name={business.name!r} "
            f"mode={business.mode} whatsapp_phone_number_id={business.whatsapp_phone_number_id}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
