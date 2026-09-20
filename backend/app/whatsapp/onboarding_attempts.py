"""The lifecycle of one Embedded Signup attempt (Sprint 82, Task 4).

Owns `WhatsAppOnboardingAttempt` rows end to end: issue a signed state,
verify and consume it exactly once when Meta's popup calls back, then record
whether the onboarding that followed succeeded or failed and why.

Three independent checks have to pass before a callback is trusted, and they
catch genuinely different attacks:

* **signature** — the state was issued by this deployment, not typed by an
  attacker. Cheap, stateless, and rejects forgeries before any query runs.
* **age** — a state captured from a browser history or a shoulder-surfed URL
  stops working after `STATE_MAX_AGE_SECONDS`.
* **single use** — the row's `consumed_at`, backed by a UNIQUE index on
  `state`. This is the one a signature can't provide: a *legitimately issued*
  state replayed a second time is still signed and still fresh, and
  re-spending an Embedded Signup authorization code means a second token
  exchange, a second `/register`, and a second webhook subscription.

`app/calendar/oauth.py` (Google) checks only the first two, which is
defensible there — its callback is idempotent — and deliberately not copied
here. This module does not import that one: sharing would mean generalizing a
working production flow to serve a flow that doesn't exist yet, for two
functions' worth of HMAC. The one piece genuinely worth sharing, loading the
signing key, is `app/whatsapp/security.py::sign`.

No Meta call and no HTTP live here — this module is the state machine only,
so the Embedded Signup provider that lands in a later sprint can be tested
against it without a network.
"""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import WhatsAppOnboardingAttempt
from app.whatsapp.security import sign

# Long enough for an owner to work through Meta's six screens (phone entry,
# waiting for an SMS code, a display name, a PIN) without the state dying
# under them — DEC-052 §2 budgets ~2 minutes for a prepared founder, so this
# is a generous multiple of that rather than a tight bound.
STATE_MAX_AGE_SECONDS = 900

# `status` values on WhatsAppOnboardingAttempt. Defined here, not on the
# model, because this module owns every transition between them.
STATUS_PENDING = "pending"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"

# Distinguishes a state this module issued from one issued by any other
# HMAC-signed flow sharing the same key (app/calendar/oauth.py's Google
# state), so a state can never be replayed across flows even though the
# signatures would verify.
_STATE_PREFIX = "wa_onboarding"

# Keep in step with WhatsAppOnboardingAttempt.state's String(255). The
# generated form is ~110 characters; this only guards against a caller
# handing us something absurd to hash and look up.
MAX_STATE_LENGTH = 255


class OnboardingStateError(RuntimeError):
    """The `state` parameter is missing, malformed, forged, expired, unknown,
    or already used. Deliberately one error for all six: the distinction
    matters for the log line, never for the caller, which refuses the
    callback identically either way."""


def _now() -> datetime:
    """Naive UTC, matching every other timestamp column in this app (see
    DEC-032's note) — the model's `expires_at`/`consumed_at` are compared
    against values from here, never against tz-aware datetimes."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _new_signed_state(business_id: uuid.UUID) -> str:
    # The nonce makes two attempts by the same business in the same second
    # distinct, which matters because `state` is a UNIQUE column — without
    # it, an impatient double-click would collide on insert rather than
    # producing two independent attempts.
    payload = f"{_STATE_PREFIX}:{business_id}:{int(time.time())}:{secrets.token_hex(16)}"
    return f"{payload}:{sign(payload)}"


def _verify_signature_and_age(state: str) -> uuid.UUID:
    if not state or len(state) > MAX_STATE_LENGTH:
        raise OnboardingStateError("Malformed state parameter")
    try:
        prefix, business_id_str, issued_at_str, nonce, signature = state.split(":")
    except ValueError as exc:
        raise OnboardingStateError("Malformed state parameter") from exc
    if prefix != _STATE_PREFIX:
        raise OnboardingStateError("Malformed state parameter")

    payload = f"{prefix}:{business_id_str}:{issued_at_str}:{nonce}"
    if not secrets.compare_digest(sign(payload), signature):
        raise OnboardingStateError("Invalid state signature")

    # Inside the try: a non-numeric timestamp is only reachable on a state
    # whose signature already verified (so: issued by us, then corrupted in
    # transit, or a format change mid-deploy), and that should surface as a
    # refused callback like every other bad state — not a 500.
    try:
        issued_at = int(issued_at_str)
    except ValueError as exc:
        raise OnboardingStateError("Malformed state parameter") from exc
    if time.time() - issued_at > STATE_MAX_AGE_SECONDS:
        raise OnboardingStateError("State parameter expired — please reconnect")

    try:
        return uuid.UUID(business_id_str)
    except ValueError as exc:
        raise OnboardingStateError("Malformed business id in state parameter") from exc


def start_attempt(db: Session, business_id: uuid.UUID) -> WhatsAppOnboardingAttempt:
    """Issue a signed, single-use state and record the attempt as pending.
    The caller hands `attempt.state` to Meta's popup and gets it back in the
    callback."""
    attempt = WhatsAppOnboardingAttempt(
        business_id=business_id,
        state=_new_signed_state(business_id),
        status=STATUS_PENDING,
        expires_at=_now() + timedelta(seconds=STATE_MAX_AGE_SECONDS),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt


def verify_and_consume_state(
    db: Session, state: str, *, business_id: uuid.UUID
) -> WhatsAppOnboardingAttempt:
    """Full validation — signature, age, single use — plus a check that the
    attempt belongs to `business_id`, the authenticated caller.

    That last check is what stops one signed-in business from completing
    another's attempt with a state they somehow obtained: the signature only
    proves this deployment issued the state, not that it issued it to the
    person now presenting it. Marks the attempt consumed and returns it.
    """
    signed_business_id = _verify_signature_and_age(state)

    attempt = db.scalars(
        select(WhatsAppOnboardingAttempt).where(WhatsAppOnboardingAttempt.state == state)
    ).first()
    if attempt is None:
        raise OnboardingStateError("Unrecognized state parameter")
    if signed_business_id != attempt.business_id or attempt.business_id != business_id:
        raise OnboardingStateError("State parameter does not belong to this business")
    if attempt.consumed_at is not None:
        raise OnboardingStateError("This connection request was already used")
    if attempt.expires_at < _now():
        raise OnboardingStateError("State parameter expired — please reconnect")

    # Claim the attempt with a conditional UPDATE rather than assigning and
    # committing (Sprint 84 review). The checks above are a read followed by
    # a write, and two callbacks arriving together — a double-clicked
    # button, a client retry racing the original — can both pass them before
    # either commits, which would spend the same authorization code twice.
    # `WHERE consumed_at IS NULL` moves the decision into the database, so
    # exactly one of any number of concurrent claims updates a row. The
    # check above stays as the fast path; this is the actual guarantee.
    claimed = db.execute(
        update(WhatsAppOnboardingAttempt)
        .where(
            WhatsAppOnboardingAttempt.id == attempt.id,
            WhatsAppOnboardingAttempt.consumed_at.is_(None),
        )
        .values(consumed_at=_now())
    )
    db.commit()
    if claimed.rowcount != 1:
        raise OnboardingStateError("This connection request was already used")

    db.refresh(attempt)
    return attempt


def complete_attempt(db: Session, attempt: WhatsAppOnboardingAttempt) -> None:
    attempt.status = STATUS_COMPLETED
    attempt.failure_reason = None
    db.commit()


def fail_attempt(db: Session, attempt: WhatsAppOnboardingAttempt, reason: str) -> None:
    """Record why an attempt failed. `reason` is engineer-facing and must
    never carry a token, a secret, or a raw Graph API response body — the
    UI maps failures to its own copy rather than showing this."""
    attempt.status = STATUS_FAILED
    attempt.failure_reason = reason
    db.commit()


def get_latest_attempt(db: Session, business_id: uuid.UUID) -> WhatsAppOnboardingAttempt | None:
    """The most recent attempt for a business — what "you started connecting
    and didn't finish" (DEC-052 §4) is answered from."""
    return db.scalars(
        select(WhatsAppOnboardingAttempt)
        .where(WhatsAppOnboardingAttempt.business_id == business_id)
        .order_by(WhatsAppOnboardingAttempt.created_at.desc())
        .limit(1)
    ).first()
