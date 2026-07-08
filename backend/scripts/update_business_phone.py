"""Idempotent update: point the existing business at the current WhatsApp number.

Updates the single business row in place (preserving its id, so seeded KB stays
linked). Keyed on old-or-new phone number id, so re-running is a no-op. Changes
only whatsapp_phone_number_id (+ ensures WABA id and autonomous mode). Thin
wrapper around `app.onboarding.bootstrap.rotate_whatsapp_number` — see that
module for the actual logic. Run from backend/:

    .venv/bin/python scripts/update_business_phone.py
"""

from app.onboarding.bootstrap import rotate_whatsapp_number

OLD_PHONE_NUMBER_ID = "1237957929400631"
NEW_PHONE_NUMBER_ID = "1270860752766508"
WABA_ID = "2511632579311134"


def main() -> None:
    try:
        business = rotate_whatsapp_number(
            old_phone_number_id=OLD_PHONE_NUMBER_ID,
            new_phone_number_id=NEW_PHONE_NUMBER_ID,
            whatsapp_business_account_id=WABA_ID,
        )
    except LookupError as exc:
        raise SystemExit(str(exc)) from exc

    print(
        f"updated: id={business.id} "
        f"whatsapp_phone_number_id={business.whatsapp_phone_number_id} "
        f"whatsapp_business_account_id={business.whatsapp_business_account_id} "
        f"mode={business.mode}"
    )


if __name__ == "__main__":
    main()
