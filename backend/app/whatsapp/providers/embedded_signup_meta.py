"""`MetaEmbeddedSignupProvider` — the real Embedded Signup flow (Sprint 83).

Owns the policy the Graph wrapper deliberately doesn't: which calls to make,
in what order, what counts as recoverable, and what gets written when they
all succeed. `app/whatsapp/graph.py` is the transport.

**What the browser is and isn't trusted for.** Meta's popup tells the page,
via postMessage, which WABA and phone number the owner picked. That message
arrives from a client, so it's treated as a hint: the token's own
`granular_scopes` (from `debug_token`) decide which WABAs this token may
touch, and Meta's own `phone_numbers` list decides which numbers exist under
it. A hint that doesn't appear in either is ignored, not honored. The only
thing the browser genuinely holds that the backend can't get elsewhere is the
authorization code — and that's useless without the app secret.

**Ordering, and why it's this order.** State is consumed first (so a replay
costs nothing and can't reach Meta at all), then the code is exchanged, then
the token is inspected, then the WABA and number are resolved and *verified*,
then tenancy is checked, and only then are the two side-effecting calls made:
`/register` (activates the number) and `subscribed_apps` (points its webhooks
at HIRA). Everything that can fail cheaply fails before anything that changes
state on Meta's side.

**Idempotency.** Re-running a completed onboarding is safe and is the
designed recovery path for a half-finished one. `subscribed_apps` is a no-op
when already subscribed, `/register` is re-issued with the *same* stored PIN
rather than a new one (Meta rejects a mismatched PIN, so generating a fresh
one would make every reconnect fail), and the credential writer is
create-or-replace. What isn't idempotent is the authorization code itself —
Meta spends it on first use — which is why each code is bound to a single-use
state row that can't be presented twice.
"""

from __future__ import annotations

import logging
import secrets
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import meta
from app.models import Business
from app.whatsapp import credentials as whatsapp_credentials
from app.whatsapp import graph, onboarding_attempts
from app.whatsapp.errors import WhatsAppNotConfiguredError
from app.whatsapp.onboarding_attempts import OnboardingStateError
from app.whatsapp.providers.base import (
    ERROR_META_UNAVAILABLE,
    ERROR_NO_PHONE_NUMBER,
    ERROR_NO_WABA,
    ERROR_PERMISSION_DENIED,
    ERROR_PHONE_NUMBER_IN_USE,
    ERROR_PIN_MISMATCH,
    ERROR_REGISTRATION_FAILED,
    ERROR_STATE_INVALID,
    ERROR_SUBSCRIPTION_FAILED,
    ERROR_TOKEN_EXCHANGE_FAILED,
    EmbeddedSignupNotConfiguredError,
    EmbeddedSignupProvider,
    EmbeddedSignupResult,
    EmbeddedSignupSession,
)

logger = logging.getLogger(__name__)

# Meta error codes this flow maps onto specific outcomes. Anything not listed
# falls through to the generic failure for its step — deliberately, rather
# than guessing at a code's meaning and showing an owner confident but wrong
# advice. See documentation/WHATSAPP_INTEGRATION.md for how to extend this.
META_ERROR_PIN_MISMATCH = 133005
META_ERROR_TOO_MANY_PIN_GUESSES = 133008
META_ERROR_PIN_ENTERED_TOO_RECENTLY = 133009
_PIN_ERRORS = {
    META_ERROR_PIN_MISMATCH,
    META_ERROR_TOO_MANY_PIN_GUESSES,
    META_ERROR_PIN_ENTERED_TOO_RECENTLY,
}


def _generate_pin() -> str:
    """A 6-digit two-step-verification PIN, generated rather than asked for —
    DEC-052 §1.3: the owner never invents or remembers one. `secrets`, not
    `random`: this value protects the number's re-registration."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _naive_utc(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(tzinfo=None)


class MetaEmbeddedSignupProvider(EmbeddedSignupProvider):
    def __init__(self, *, client: httpx.Client | None = None) -> None:
        """`client` exists so tests drive an `httpx.MockTransport`, the same
        injection `verify_whatsapp_credentials` already uses. In production
        it's None and each `complete()` opens and closes its own."""
        self._client = client

    def _require_configured(self) -> None:
        if not meta.tech_provider_configured():
            raise EmbeddedSignupNotConfiguredError(
                "Embedded Signup isn't configured on this deployment — "
                "META_APP_ID, META_APP_SECRET and META_APP_CONFIG_ID must all be set."
            )

    def start(self, db: Session, *, business_id: uuid.UUID) -> EmbeddedSignupSession:
        """Issue a signed, single-use, expiring state and hand the frontend
        the configuration id its JS SDK call needs. Nothing is contacted at
        Meta here — the popup itself is what talks to them next."""
        self._require_configured()
        try:
            attempt = onboarding_attempts.start_attempt(db, business_id)
        except WhatsAppNotConfiguredError as exc:
            # The signing/encryption key is missing, so no state can be
            # issued. Production can't boot without it (_REQUIRED_IN_
            # PRODUCTION), but a local or staging box can — and it should
            # say "not configured" rather than 500 on an unhandled error.
            raise EmbeddedSignupNotConfiguredError(str(exc)) from exc
        logger.info(
            "whatsapp.onboarding.started business_id=%s method=embedded_signup attempt_id=%s",
            business_id,
            attempt.id,
        )
        return EmbeddedSignupSession(config_id=meta.config_id(), state=attempt.state)

    def complete(  # noqa: C901 — a linear sequence of Meta steps, not branching logic
        self,
        db: Session,
        *,
        business_id: uuid.UUID,
        authorization_code: str,
        state: str,
        waba_id: str | None = None,
        phone_number_id: str | None = None,
    ) -> EmbeddedSignupResult:
        self._require_configured()

        try:
            attempt = onboarding_attempts.verify_and_consume_state(
                db, state, business_id=business_id
            )
        except OnboardingStateError as exc:
            # Nothing has been spent yet — no Meta call, no write. A replay,
            # a forged state and an expired one all land here and are all
            # answered the same way: start again.
            logger.warning(
                "whatsapp.onboarding.failed business_id=%s method=embedded_signup "
                "step=state reason=%s",
                business_id,
                exc,
            )
            return EmbeddedSignupResult(
                success=False, error=str(exc), error_code=ERROR_STATE_INVALID
            )

        owns_client = self._client is None
        client = self._client or graph.new_client()
        try:
            return self._run(
                db,
                client,
                attempt=attempt,
                business_id=business_id,
                authorization_code=authorization_code,
                waba_hint=waba_id,
                phone_number_hint=phone_number_id,
            )
        except WhatsAppNotConfiguredError as exc:
            # The encryption key is missing, so credentials can't be stored.
            # A deployment problem, not the owner's — and not something a
            # retry fixes, so it isn't reported as a transient Meta failure.
            onboarding_attempts.fail_attempt(db, attempt, "encryption_not_configured")
            raise EmbeddedSignupNotConfiguredError(str(exc)) from exc
        finally:
            if owns_client:
                client.close()

    def _run(
        self,
        db: Session,
        client: httpx.Client,
        *,
        attempt,
        business_id: uuid.UUID,
        authorization_code: str,
        waba_hint: str | None,
        phone_number_hint: str | None,
    ) -> EmbeddedSignupResult:
        def fail(code: str, reason: str) -> EmbeddedSignupResult:
            onboarding_attempts.fail_attempt(db, attempt, reason)
            logger.warning(
                "whatsapp.onboarding.failed business_id=%s method=embedded_signup "
                "error_code=%s reason=%s",
                business_id,
                code,
                reason,
            )
            return EmbeddedSignupResult(success=False, error=reason, error_code=code)

        # 1. Authorization code -> the business's own token.
        try:
            token = graph.exchange_code_for_token(authorization_code, client=client)
        except graph.GraphError as exc:
            return fail(
                ERROR_META_UNAVAILABLE if exc.retryable else ERROR_TOKEN_EXCHANGE_FAILED,
                exc.reason,
            )

        # 2. What is this token actually allowed to do?
        try:
            info = graph.debug_token(token, client=client)
        except graph.GraphError as exc:
            return fail(
                ERROR_META_UNAVAILABLE if exc.retryable else ERROR_TOKEN_EXCHANGE_FAILED,
                exc.reason,
            )

        if not info.is_valid:
            return fail(ERROR_TOKEN_EXCHANGE_FAILED, "meta reported the exchanged token as invalid")
        if info.missing_scopes:
            # The owner unticked a permission on Meta's consent screen. The
            # scope names are logged for support and never shown to them.
            return fail(
                ERROR_PERMISSION_DENIED,
                f"missing_scopes={','.join(sorted(info.missing_scopes))}",
            )

        # 3. Resolve the WABA. The token's granular scopes are authoritative
        #    whenever they say anything; the popup's hint may only *choose
        #    among* what they already permit.
        resolved_waba = self._resolve_waba(info.waba_ids, waba_hint)

        # Sprint 84, from live Meta responses: `granular_scopes` really can
        # come back with no `target_ids` at all (verified against a real
        # SYSTEM_USER token — see DEC-062). When Meta scopes the token to no
        # specific object, there is nothing to choose among, and refusing
        # every such token would fail onboarding outright. The hint is then
        # allowed through *only* as a candidate, and the `get_waba` call
        # below — made with this business's own token — is what proves the
        # token can actually reach it. An unauthorized id 4xxs there and is
        # refused. What this never does is skip verification: it changes
        # which call does the verifying, not whether one happens.
        verified_by_lookup = False
        if resolved_waba is None and waba_hint and not info.waba_ids:
            resolved_waba = waba_hint
            verified_by_lookup = True

        if resolved_waba is None:
            return fail(
                ERROR_NO_WABA,
                f"no authorized WABA on token (hint={'yes' if waba_hint else 'no'}, "
                f"granular_targets={len(info.waba_ids)})",
            )

        try:
            waba = graph.get_waba(resolved_waba, token, client=client)
            numbers = graph.list_phone_numbers(resolved_waba, token, client=client)
        except graph.GraphError as exc:
            if verified_by_lookup and not exc.retryable:
                return fail(
                    ERROR_NO_WABA, f"hinted WABA not reachable with this token: {exc.reason}"
                )
            return fail(ERROR_META_UNAVAILABLE if exc.retryable else ERROR_NO_WABA, exc.reason)

        if verified_by_lookup:
            logger.info(
                "whatsapp.onboarding.waba_verified_by_lookup business_id=%s waba_id=%s",
                business_id,
                waba.id,
            )

        # 4. Resolve the phone number against what Meta says actually exists.
        number = self._resolve_phone_number(numbers, phone_number_hint)
        if number is None:
            return fail(
                ERROR_NO_PHONE_NUMBER,
                f"no usable phone number under waba (count={len(numbers)})",
            )

        # 5. Tenancy: one Meta phone number routes to exactly one business,
        #    because the webhook looks a business up by it. Checked before
        #    /register so a losing attempt changes nothing on Meta's side.
        conflicting = db.scalars(
            select(Business.id).where(
                Business.whatsapp_phone_number_id == number.id,
                Business.id != business_id,
            )
        ).first()
        if conflicting is not None:
            return fail(
                ERROR_PHONE_NUMBER_IN_USE, "phone number already connected to another business"
            )

        # 6. Activate the number. Reuses this business's existing PIN when it
        #    has one, so a reconnect doesn't collide with the PIN already set.
        existing_credential = whatsapp_credentials.get_stored_credential(db, business_id)
        pin = (
            whatsapp_credentials.get_two_factor_pin(existing_credential)
            if existing_credential is not None
            else None
        ) or _generate_pin()

        try:
            graph.register_phone_number(number.id, pin, token, client=client)
        except graph.GraphError as exc:
            if exc.code in _PIN_ERRORS:
                # The number carries a two-step PIN HIRA didn't set (or can't
                # match). Nothing here can resolve that — it needs the owner
                # to clear it in WhatsApp Manager.
                return fail(ERROR_PIN_MISMATCH, exc.reason)
            return fail(
                ERROR_META_UNAVAILABLE if exc.retryable else ERROR_REGISTRATION_FAILED, exc.reason
            )

        # 7. Point the WABA's webhooks at HIRA. Without this, Meta accepts the
        #    customer's messages and delivers them nowhere.
        try:
            graph.subscribe_app(resolved_waba, token, client=client)
        except graph.GraphError as exc:
            return fail(
                ERROR_META_UNAVAILABLE if exc.retryable else ERROR_SUBSCRIPTION_FAILED, exc.reason
            )

        # 8. Persist. Credential first, then the business row, then the
        #    attempt — each commits, and re-running repeats all three
        #    harmlessly if the process dies between them.
        whatsapp_credentials.store_embedded_signup_credentials(
            db,
            business_id,
            access_token=token,
            token_type=info.token_type,
            granted_scopes=" ".join(info.scopes) if info.scopes else None,
            token_expires_at=_naive_utc(info.expires_at) if info.expires_at else None,
            two_factor_pin=pin,
        )

        business = db.get(Business, business_id)
        business.whatsapp_phone_number_id = number.id
        business.whatsapp_business_account_id = waba.id
        business.meta_business_id = waba.owner_business_id
        business.whatsapp_display_phone_number = number.display_phone_number
        business.whatsapp_connection_status = "connected"
        business.whatsapp_registration_status = "registered"
        db.commit()

        onboarding_attempts.complete_attempt(db, attempt)
        logger.info(
            "whatsapp.onboarding.completed business_id=%s method=embedded_signup "
            "waba_id=%s token_type=%s",
            business_id,
            waba.id,
            info.token_type,
        )
        return EmbeddedSignupResult(
            success=True,
            phone_number_id=number.id,
            whatsapp_business_account_id=waba.id,
            display_phone_number=number.display_phone_number,
        )

    @staticmethod
    def _resolve_waba(authorized: tuple[str, ...], hint: str | None) -> str | None:
        """The hint wins only if the token actually grants it. Otherwise the
        single authorized WABA is used; with several and no valid hint there
        is no safe way to choose, so none is chosen."""
        if hint and hint in authorized:
            return hint
        if len(authorized) == 1:
            return authorized[0]
        return None

    @staticmethod
    def _resolve_phone_number(
        numbers: list[graph.PhoneNumber], hint: str | None
    ) -> graph.PhoneNumber | None:
        """Same rule one level down: the popup's phone number id is honored
        only if Meta lists it under this WABA."""
        if hint:
            for number in numbers:
                if number.id == hint:
                    return number
            return None
        if len(numbers) == 1:
            return numbers[0]
        return None
