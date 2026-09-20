"""Tech Provider foundation (Sprint 82): the dual-architecture webhook, the
Meta configuration module, and the onboarding-attempt state machine.

The webhook tests here are the ones that matter most in this sprint. Before
it, `app/webhooks/whatsapp.py` verified every delivery against the calling
business's own stored app secret — correct for guided-manual customers, and
silently fatal for Embedded Signup ones, whose webhooks Meta signs with
Stoneveil's `META_APP_SECRET`. Their messages would have 403'd forever while
the dashboard showed "Connected."
"""

import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app import meta
from app.core.config import settings
from app.db.session import get_db
from app.main import app
from app.models import Business, WhatsAppCredential, WhatsAppOnboardingAttempt
from app.webhooks.whatsapp import get_reply_dispatcher
from app.whatsapp import onboarding_attempts
from app.whatsapp.credentials import (
    get_stored_credential,
    get_webhook_signing_secret,
    store_credentials,
)
from app.whatsapp.onboarding_attempts import OnboardingStateError
from app.whatsapp.security import encrypt_secret

BUSINESS_APP_SECRET = "the-businesss-own-app-secret"
STONEVEIL_APP_SECRET = "stoneveils-tech-provider-app-secret"


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())


@pytest.fixture(autouse=True)
def _stoneveil_app(monkeypatch):
    monkeypatch.setattr(settings, "meta_app_secret", STONEVEIL_APP_SECRET)


def _client(db_session):
    dispatched: list[tuple] = []

    def fake_dispatcher():
        def dispatch(background_tasks, conversation_id, message_id, user_text):
            dispatched.append((conversation_id, message_id, user_text))

        return dispatch

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_reply_dispatcher] = fake_dispatcher
    return TestClient(app), dispatched


def _manual_business(db, phone_number_id="PN-MANUAL") -> Business:
    business = Business(name="Manual Clinic", whatsapp_phone_number_id=phone_number_id)
    db.add(business)
    db.flush()
    store_credentials(db, business.id, access_token="manual-token", app_secret=BUSINESS_APP_SECRET)
    db.commit()
    return business


def _embedded_signup_business(db, phone_number_id="PN-ES") -> Business:
    """What the Embedded Signup provider will write once it exists: a
    per-business access token, no per-business app secret at all."""
    business = Business(name="Embedded Clinic", whatsapp_phone_number_id=phone_number_id)
    db.add(business)
    db.flush()
    db.add(
        WhatsAppCredential(
            business_id=business.id,
            access_token_encrypted=encrypt_secret("business-integration-token"),
            app_secret_encrypted=None,
            token_source=meta.TOKEN_SOURCE_EMBEDDED_SIGNUP,
        )
    )
    db.commit()
    return business


def _sign(body: bytes, app_secret: str) -> str:
    return f"sha256={hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()}"


def _payload(phone_number_id: str, wa_message_id: str) -> dict:
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": phone_number_id},
                            "contacts": [
                                {"wa_id": "+15551230000", "profile": {"name": "Test User"}}
                            ],
                            "messages": [
                                {
                                    "id": wa_message_id,
                                    "from": "+15551230000",
                                    "type": "text",
                                    "text": {"body": "hello"},
                                }
                            ],
                        }
                    }
                ]
            }
        ]
    }


def _post(client, payload: dict, app_secret: str):
    body = json.dumps(payload).encode()
    return client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={
            "X-Hub-Signature-256": _sign(body, app_secret),
            "Content-Type": "application/json",
        },
    )


# --- Task 1: both onboarding architectures verify, and only with the right key


def test_manual_business_still_verifies_with_its_own_app_secret(db_session):
    """The regression guard for this whole sprint: guided-manual v1 is
    production today and must be untouched by Tech Provider support."""
    business = _manual_business(db_session)
    client, dispatched = _client(db_session)
    try:
        resp = _post(
            client,
            _payload(business.whatsapp_phone_number_id, "wamid.manual.1"),
            BUSINESS_APP_SECRET,
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert len(dispatched) == 1


def test_embedded_signup_business_verifies_with_stoneveils_app_secret(db_session):
    """The bug this sprint exists to fix. Meta signs a Tech Provider
    customer's webhooks with Stoneveil's app secret; before Sprint 82 this
    delivery 403'd with no per-business secret to check it against."""
    business = _embedded_signup_business(db_session)
    client, dispatched = _client(db_session)
    try:
        resp = _post(
            client,
            _payload(business.whatsapp_phone_number_id, "wamid.es.1"),
            STONEVEIL_APP_SECRET,
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert len(dispatched) == 1


def test_embedded_signup_business_rejects_a_businesss_own_secret(db_session):
    """The secrets are not interchangeable: resolving the wrong one must
    fail closed, not fall through to trying the other."""
    business = _embedded_signup_business(db_session)
    client, _ = _client(db_session)
    try:
        resp = _post(
            client,
            _payload(business.whatsapp_phone_number_id, "wamid.es.2"),
            BUSINESS_APP_SECRET,
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 403


def test_manual_business_rejects_stoneveils_secret(db_session):
    business = _manual_business(db_session, phone_number_id="PN-MANUAL-2")
    client, _ = _client(db_session)
    try:
        resp = _post(
            client,
            _payload(business.whatsapp_phone_number_id, "wamid.manual.2"),
            STONEVEIL_APP_SECRET,
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 403


def test_embedded_signup_rejected_when_meta_app_secret_is_unset(db_session, monkeypatch):
    """A deployment that hasn't configured META_APP_SECRET cannot verify
    these deliveries at all. Unverifiable must mean rejected — never
    accepted, and never verified against an empty-string secret."""
    monkeypatch.setattr(settings, "meta_app_secret", "")
    business = _embedded_signup_business(db_session, phone_number_id="PN-ES-3")
    client, _ = _client(db_session)
    try:
        resp = _post(client, _payload(business.whatsapp_phone_number_id, "wamid.es.3"), "")
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 403


def test_signing_secret_resolution_is_driven_by_token_source(db_session):
    manual = _manual_business(db_session, phone_number_id="PN-R1")
    embedded = _embedded_signup_business(db_session, phone_number_id="PN-R2")

    manual_credential = get_stored_credential(db_session, manual.id)
    embedded_credential = get_stored_credential(db_session, embedded.id)

    assert manual_credential.token_source == meta.TOKEN_SOURCE_MANUAL
    assert embedded_credential.token_source == meta.TOKEN_SOURCE_EMBEDDED_SIGNUP
    assert get_webhook_signing_secret(manual_credential) == BUSINESS_APP_SECRET
    assert get_webhook_signing_secret(embedded_credential) == STONEVEIL_APP_SECRET


def test_reconnecting_manually_moves_an_embedded_signup_row_back_to_manual(db_session):
    """Otherwise the row keeps claiming `embedded_signup` while Meta has
    started signing with the business's own app secret again — every
    subsequent inbound message would be verified against the wrong key."""
    business = _embedded_signup_business(db_session, phone_number_id="PN-SWAP")
    store_credentials(
        db_session, business.id, access_token="manual-token", app_secret=BUSINESS_APP_SECRET
    )

    credential = get_stored_credential(db_session, business.id)
    assert credential.token_source == meta.TOKEN_SOURCE_MANUAL
    assert get_webhook_signing_secret(credential) == BUSINESS_APP_SECRET


# --- Task 5: one source of truth for Meta configuration ------------------


def test_graph_url_joins_base_version_and_path():
    assert meta.graph_url("PN1", "messages") == "https://graph.facebook.com/v21.0/PN1/messages"
    assert meta.graph_url() == "https://graph.facebook.com/v21.0"


def test_graph_url_follows_configured_version(monkeypatch):
    """Bumping the Graph version has to be a one-line change — the point of
    centralizing it. If any module rebuilds its own URL, this misses it, but
    no module does: grep for whatsapp_graph_version outside app/meta.py."""
    monkeypatch.setattr(settings, "whatsapp_graph_version", "v23.0")
    assert meta.graph_url("X") == "https://graph.facebook.com/v23.0/X"


def test_tech_provider_requires_all_three_values(monkeypatch):
    monkeypatch.setattr(settings, "meta_app_id", "123")
    monkeypatch.setattr(settings, "meta_app_secret", "secret")
    monkeypatch.setattr(settings, "meta_app_config_id", "")
    assert meta.tech_provider_configured() is False

    monkeypatch.setattr(settings, "meta_app_config_id", "cfg-1")
    assert meta.tech_provider_configured() is True


# --- Task 4: onboarding attempts ----------------------------------------


def _business(db) -> Business:
    business = Business(name="Attempt Co")
    db.add(business)
    db.commit()
    return business


def test_start_attempt_persists_a_pending_signed_state(db_session):
    business = _business(db_session)
    attempt = onboarding_attempts.start_attempt(db_session, business.id)

    assert attempt.status == onboarding_attempts.STATUS_PENDING
    assert attempt.consumed_at is None
    assert str(business.id) in attempt.state
    assert attempt.expires_at > datetime.now(timezone.utc).replace(tzinfo=None)


def test_state_round_trips_and_is_consumed(db_session):
    business = _business(db_session)
    attempt = onboarding_attempts.start_attempt(db_session, business.id)

    consumed = onboarding_attempts.verify_and_consume_state(
        db_session, attempt.state, business_id=business.id
    )
    assert consumed.id == attempt.id
    assert consumed.consumed_at is not None


def test_state_cannot_be_used_twice(db_session):
    """Single-use is the guarantee a signature alone can't give, and the
    reason this table exists: replaying a callback would re-spend the
    authorization code on a second token exchange and /register."""
    business = _business(db_session)
    attempt = onboarding_attempts.start_attempt(db_session, business.id)
    onboarding_attempts.verify_and_consume_state(db_session, attempt.state, business_id=business.id)

    with pytest.raises(OnboardingStateError, match="already used"):
        onboarding_attempts.verify_and_consume_state(
            db_session, attempt.state, business_id=business.id
        )


def test_tampered_state_is_rejected(db_session):
    business = _business(db_session)
    attempt = onboarding_attempts.start_attempt(db_session, business.id)
    forged = attempt.state[:-1] + ("0" if attempt.state[-1] != "0" else "1")

    with pytest.raises(OnboardingStateError, match="signature"):
        onboarding_attempts.verify_and_consume_state(db_session, forged, business_id=business.id)


@pytest.mark.parametrize(
    "state",
    ["", "not-a-state", "wa_onboarding:only:three:parts", "other_flow:a:1:b:c"],
)
def test_malformed_state_is_rejected(db_session, state):
    business = _business(db_session)
    with pytest.raises(OnboardingStateError):
        onboarding_attempts.verify_and_consume_state(db_session, state, business_id=business.id)


def test_expired_state_is_rejected(db_session):
    business = _business(db_session)
    attempt = onboarding_attempts.start_attempt(db_session, business.id)
    attempt.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    db_session.commit()

    with pytest.raises(OnboardingStateError, match="expired"):
        onboarding_attempts.verify_and_consume_state(
            db_session, attempt.state, business_id=business.id
        )


def test_another_business_cannot_consume_an_attempt(db_session):
    """A signature proves this deployment issued the state, not that it
    issued it to whoever is now presenting it."""
    owner = _business(db_session)
    intruder = Business(name="Intruder Co")
    db_session.add(intruder)
    db_session.commit()

    attempt = onboarding_attempts.start_attempt(db_session, owner.id)
    with pytest.raises(OnboardingStateError, match="does not belong"):
        onboarding_attempts.verify_and_consume_state(
            db_session, attempt.state, business_id=intruder.id
        )


def test_unknown_state_is_rejected(db_session):
    """Correctly signed for a business that has no attempt row — what a
    replay after the row was deleted, or a state minted by a rolled-back
    deploy, looks like."""
    business = _business(db_session)
    attempt = onboarding_attempts.start_attempt(db_session, business.id)
    state = attempt.state
    db_session.delete(attempt)
    db_session.commit()

    with pytest.raises(OnboardingStateError, match="Unrecognized"):
        onboarding_attempts.verify_and_consume_state(db_session, state, business_id=business.id)


def test_complete_and_fail_record_the_outcome(db_session):
    business = _business(db_session)
    attempt = onboarding_attempts.start_attempt(db_session, business.id)
    onboarding_attempts.fail_attempt(db_session, attempt, "meta_error_code=131000")
    assert attempt.status == onboarding_attempts.STATUS_FAILED
    assert attempt.failure_reason == "meta_error_code=131000"

    retry = onboarding_attempts.start_attempt(db_session, business.id)
    onboarding_attempts.complete_attempt(db_session, retry)
    assert retry.status == onboarding_attempts.STATUS_COMPLETED
    assert retry.failure_reason is None


def test_latest_attempt_is_the_most_recent(db_session):
    business = _business(db_session)
    onboarding_attempts.start_attempt(db_session, business.id)
    second = onboarding_attempts.start_attempt(db_session, business.id)

    latest = onboarding_attempts.get_latest_attempt(db_session, business.id)
    assert latest is not None
    assert latest.id == second.id


def test_attempts_are_deleted_with_their_business(db_session):
    business = _business(db_session)
    onboarding_attempts.start_attempt(db_session, business.id)
    db_session.delete(business)
    db_session.commit()

    assert db_session.query(WhatsAppOnboardingAttempt).count() == 0


def test_get_latest_attempt_is_none_for_a_business_that_never_started(db_session):
    assert onboarding_attempts.get_latest_attempt(db_session, uuid.uuid4()) is None


def test_consuming_an_attempt_is_an_atomic_claim(db_session):
    """Sprint 84 review: the single-use guarantee must not be a read
    followed by a write. Two concurrent callbacks can both pass an
    in-Python `consumed_at is None` check; only one can win a conditional
    UPDATE. This asserts the mechanism the code now relies on."""
    from sqlalchemy import update

    from app.models import WhatsAppOnboardingAttempt

    business = _business(db_session)
    attempt = onboarding_attempts.start_attempt(db_session, business.id)

    def claim() -> int:
        result = db_session.execute(
            update(WhatsAppOnboardingAttempt)
            .where(
                WhatsAppOnboardingAttempt.id == attempt.id,
                WhatsAppOnboardingAttempt.consumed_at.is_(None),
            )
            .values(consumed_at=datetime.now(timezone.utc).replace(tzinfo=None))
        )
        db_session.commit()
        return result.rowcount

    assert claim() == 1
    assert claim() == 0
