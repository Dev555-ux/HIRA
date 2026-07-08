"""Additive seed: one autonomous business wired to the live WhatsApp number.

Idempotent — if a business with this whatsapp_phone_number_id already exists it is
updated to autonomous mode rather than duplicated. Thin wrapper around
`app.onboarding.bootstrap.seed_business` — see that module for the actual
logic. Run from the backend/ directory:

    .venv/bin/python scripts/seed_business.py
"""

from app.onboarding.bootstrap import seed_business

PHONE_NUMBER_ID = "1237957929400631"
WABA_ID = "2511632579311134"
BUSINESS_NAME = "HIRA Test Business"


def main() -> None:
    business, action = seed_business(
        name=BUSINESS_NAME,
        phone_number_id=PHONE_NUMBER_ID,
        whatsapp_business_account_id=WABA_ID,
    )
    print(
        f"{action}: id={business.id} name={business.name!r} "
        f"mode={business.mode} whatsapp_phone_number_id={business.whatsapp_phone_number_id}"
    )


if __name__ == "__main__":
    main()
