"""Additive, idempotent seed of realistic knowledge for the autonomous business.

Thin wrapper around `app.onboarding.bootstrap.seed_knowledge_base` — see that
module (and `app.onboarding.knowledge` for the fact list, `app.onboarding.
verification` for business resolution) for the actual logic. Idempotent:
facts already present (matched by title) are skipped. Run from backend/:

    .venv/bin/python scripts/seed_knowledge_base.py

Business resolution has no hardcoded phone number id (that goes stale across
number rotations — see scripts/update_business_phone.py). Instead:
  1. If there's exactly one Business row, use it.
  2. Otherwise, set PHONE_NUMBER_ID to pick one by whatsapp_phone_number_id
     (the same field/lookup the webhook uses — see app/webhooks/whatsapp.py):
         PHONE_NUMBER_ID=1270860752766508 .venv/bin/python scripts/seed_knowledge_base.py
  3. If multiple businesses exist and PHONE_NUMBER_ID isn't set, this exits
     with an error listing the candidates instead of guessing.
"""

import os

from app.onboarding.bootstrap import seed_knowledge_base


def main() -> None:
    phone_number_id = os.environ.get("PHONE_NUMBER_ID")
    try:
        business, inserted, total = seed_knowledge_base(phone_number_id=phone_number_id)
    except LookupError as exc:
        raise SystemExit(str(exc)) from exc

    print(f"inserted {inserted} new fact(s); total kb rows for business {business.id}: {total}")


if __name__ == "__main__":
    main()
