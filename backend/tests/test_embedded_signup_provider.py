"""Integration tests for the real Embedded Signup provider (Sprint 83).

Every Meta call is driven through an `httpx.MockTransport`, the same
injection `verify_whatsapp_credentials` and the Instagram OAuth flow already
use — no network, but the provider's own request-building, response-parsing
and error-mapping all run for real. What's mocked is Meta, not HIRA.

`_meta()` below builds a router keyed on (method, path) so each test states
only the responses it cares about and any unexpected call fails loudly
rather than silently returning a default — a test that passes because a step
was never reached is worse than no test.
"""

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from cryptography.fernet import Fernet

from app import meta
from app.core.config import settings
from app.models import Business, WhatsAppCredential
from app.whatsapp import credentials as whatsapp_credentials
from app.whatsapp import onboarding_attempts
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
)
from app.whatsapp.providers.embedded_signup_meta import MetaEmbeddedSignupProvider

WABA_ID = "111111111111111"
PHONE_NUMBER_ID = "222222222222222"
OWNER_BUSINESS_ID = "333333333333333"
DISPLAY_NUMBER = "+1 555 010 0000"
TOKEN = "EAABusinessIntegrationToken"


@pytest.fixture(autouse=True)
def _tech_provider_configured(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())
    monkeypatch.setattr(settings, "meta_app_id", "898692016617650")
    monkeypatch.setattr(settings, "meta_app_secret", "stoneveil-app-secret")
    monkeypatch.setattr(settings, "meta_app_config_id", "config-1")


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch):
    """The retry path is asserted for behaviour, not for wall-clock delay."""
    monkeypatch.setattr("app.whatsapp.graph.time.sleep", lambda _seconds: None)


def _business(db, name="Clinic", **kwargs) -> Business:
    business = Business(name=name, **kwargs)
    db.add(business)
    db.commit()
    return business


def _debug_token_payload(
    *,
    scopes=("whatsapp_business_management", "whatsapp_business_messaging"),
    waba_ids=(WABA_ID,),
    is_valid=True,
    expires_at=0,
    token_type="SYSTEM_USER",
):
    return {
        "data": {
            "app_id": "898692016617650",
            "type": token_type,
            "is_valid": is_valid,
            "expires_at": expires_at,
            "scopes": list(scopes),
            "granular_scopes": [
                {"scope": "whatsapp_business_management", "target_ids": list(waba_ids)}
            ],
        }
    }


def _phone_numbers_payload(numbers=None):
    numbers = numbers if numbers is not None else [(PHONE_NUMBER_ID, DISPLAY_NUMBER)]
    return {
        "data": [
            {
                "id": number_id,
                "display_phone_number": display,
                "verified_name": "Clinic",
                "code_verification_status": "VERIFIED",
            }
            for number_id, display in numbers
        ]
    }


def _meta_handler(overrides=None, *, calls=None):
    """The Graph API router as a plain callable, so a test can wrap it (see
    the reconnect test, which inspects the PIN on its way through) without
    reaching into MockTransport's internals. `overrides` maps a path suffix
    to either a dict (200) or an `httpx.Response`."""
    overrides = overrides or {}
    defaults = {
        "oauth/access_token": {"access_token": TOKEN, "token_type": "bearer"},
        "debug_token": _debug_token_payload(),
        WABA_ID + "/phone_numbers": _phone_numbers_payload(),
        WABA_ID: {
            "id": WABA_ID,
            "name": "Clinic WABA",
            "owner_business_info": {"id": OWNER_BUSINESS_ID},
        },
        PHONE_NUMBER_ID + "/register": {"success": True},
        WABA_ID + "/subscribed_apps": {"success": True},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.split("/v", 1)[-1]
        path = path.split("/", 1)[-1] if "/" in path else path
        if calls is not None:
            calls.append((request.method, path))

        for key in sorted({**defaults, **overrides}, key=len, reverse=True):
            if path == key:
                value = overrides.get(key, defaults.get(key))
                if isinstance(value, httpx.Response):
                    return value
                return httpx.Response(200, json=value)
        raise AssertionError(f"unexpected Meta call: {request.method} {request.url}")

    return handler


def _meta(overrides=None, *, calls=None):
    return httpx.Client(transport=httpx.MockTransport(_meta_handler(overrides, calls=calls)))


def _error(status_code: int, code: int | None = None, subcode: int | None = None):
    body = {"error": {"message": "should never be shown", "type": "OAuthException"}}
    if code is not None:
        body["error"]["code"] = code
    if subcode is not None:
        body["error"]["error_subcode"] = subcode
    return httpx.Response(status_code, json=body)


def _provider(client):
    return MetaEmbeddedSignupProvider(client=client)


def _start(db, business) -> str:
    return _provider(_meta()).start(db, business_id=business.id).state


# --- happy path -----------------------------------------------------------


def test_successful_embedded_signup_persists_everything(db_session):
    business = _business(db_session)
    calls: list[tuple[str, str]] = []
    provider = _provider(_meta(calls=calls))
    state = _start(db_session, business)

    result = provider.complete(
        db_session,
        business_id=business.id,
        authorization_code="auth-code",
        state=state,
        waba_id=WABA_ID,
        phone_number_id=PHONE_NUMBER_ID,
    )

    assert result.success is True
    assert result.phone_number_id == PHONE_NUMBER_ID
    assert result.whatsapp_business_account_id == WABA_ID
    assert result.display_phone_number == DISPLAY_NUMBER
    assert result.error_code is None

    db_session.refresh(business)
    assert business.whatsapp_phone_number_id == PHONE_NUMBER_ID
    assert business.whatsapp_business_account_id == WABA_ID
    assert business.meta_business_id == OWNER_BUSINESS_ID
    assert business.whatsapp_display_phone_number == DISPLAY_NUMBER
    assert business.whatsapp_connection_status == "connected"
    assert business.whatsapp_registration_status == "registered"

    credential = whatsapp_credentials.get_stored_credential(db_session, business.id)
    assert credential.token_source == meta.TOKEN_SOURCE_EMBEDDED_SIGNUP
    assert credential.token_type == "SYSTEM_USER"
    assert credential.granted_scopes == "whatsapp_business_management whatsapp_business_messaging"
    # expires_at=0 means "never expires" — must not be stored as epoch 0.
    assert credential.token_expires_at is None
    assert whatsapp_credentials.get_access_token(credential) == TOKEN
    assert credential.app_secret_encrypted is None
    pin = whatsapp_credentials.get_two_factor_pin(credential)
    assert pin is not None and len(pin) == 6 and pin.isdigit()

    # Both side-effecting calls actually happened, in the right order.
    assert ("POST", f"{PHONE_NUMBER_ID}/register") in calls
    assert ("POST", f"{WABA_ID}/subscribed_apps") in calls
    assert calls.index(("POST", f"{PHONE_NUMBER_ID}/register")) < calls.index(
        ("POST", f"{WABA_ID}/subscribed_apps")
    )

    attempt = onboarding_attempts.get_latest_attempt(db_session, business.id)
    assert attempt.status == onboarding_attempts.STATUS_COMPLETED


def test_real_token_expiry_is_stored(db_session):
    business = _business(db_session)
    expires_at = int((datetime.now(timezone.utc) + timedelta(days=60)).timestamp())
    provider = _provider(_meta({"debug_token": _debug_token_payload(expires_at=expires_at)}))
    state = _start(db_session, business)

    assert provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    ).success

    credential = whatsapp_credentials.get_stored_credential(db_session, business.id)
    assert credential.token_expires_at is not None
    expected = datetime.fromtimestamp(expires_at, tz=timezone.utc).replace(tzinfo=None)
    assert abs((credential.token_expires_at - expected).total_seconds()) < 2


def test_waba_and_phone_resolve_without_any_popup_hints(db_session):
    """The postMessage payload is optional — a token authorizing exactly one
    WABA with one number is unambiguous on its own."""
    business = _business(db_session)
    provider = _provider(_meta())
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is True
    assert result.phone_number_id == PHONE_NUMBER_ID


# --- state: replay, expiry, tampering, cross-tenant -----------------------


def test_replayed_state_is_refused_and_reaches_no_meta_call(db_session):
    """A duplicate callback — a double-clicked button, a retried request —
    must not re-spend the authorization code. Meta is never contacted: the
    transport raises on any call, so reaching one fails this test."""
    business = _business(db_session)
    state = _start(db_session, business)
    _provider(_meta()).complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    def no_calls(request):
        raise AssertionError("a replayed state must not reach Meta")

    replay = MetaEmbeddedSignupProvider(
        client=httpx.Client(transport=httpx.MockTransport(no_calls))
    )
    result = replay.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_STATE_INVALID


def test_expired_state_is_refused(db_session):
    business = _business(db_session)
    provider = _provider(_meta())
    attempt = onboarding_attempts.start_attempt(db_session, business.id)
    attempt.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
    db_session.commit()

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=attempt.state
    )

    assert result.success is False
    assert result.error_code == ERROR_STATE_INVALID


def test_tampered_state_is_refused(db_session):
    business = _business(db_session)
    state = _start(db_session, business)
    forged = state[:-1] + ("0" if state[-1] != "0" else "1")

    result = _provider(_meta()).complete(
        db_session, business_id=business.id, authorization_code="c", state=forged
    )

    assert result.success is False
    assert result.error_code == ERROR_STATE_INVALID


def test_another_business_cannot_complete_someone_elses_attempt(db_session):
    owner = _business(db_session, name="Owner")
    intruder = _business(db_session, name="Intruder")
    state = _start(db_session, owner)

    result = _provider(_meta()).complete(
        db_session, business_id=intruder.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_STATE_INVALID
    assert whatsapp_credentials.get_stored_credential(db_session, intruder.id) is None


# --- Meta-side failures ---------------------------------------------------


def test_invalid_authorization_code_fails_without_persisting(db_session):
    business = _business(db_session)
    provider = _provider(_meta({"oauth/access_token": _error(400, code=100)}))
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="bad", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_TOKEN_EXCHANGE_FAILED
    assert whatsapp_credentials.get_stored_credential(db_session, business.id) is None
    db_session.refresh(business)
    assert business.whatsapp_connection_status == "not_connected"
    attempt = onboarding_attempts.get_latest_attempt(db_session, business.id)
    assert attempt.status == onboarding_attempts.STATUS_FAILED
    assert attempt.failure_reason


def test_token_exchange_response_without_a_token_fails(db_session):
    business = _business(db_session)
    provider = _provider(_meta({"oauth/access_token": {"token_type": "bearer"}}))
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_TOKEN_EXCHANGE_FAILED


def test_missing_scopes_are_reported_as_permission_denied(db_session):
    """The owner unticked a permission on Meta's consent screen."""
    business = _business(db_session)
    provider = _provider(
        _meta({"debug_token": _debug_token_payload(scopes=("whatsapp_business_management",))})
    )
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_PERMISSION_DENIED
    assert whatsapp_credentials.get_stored_credential(db_session, business.id) is None


def test_conversions_scope_is_not_required_to_connect(db_session):
    """`whatsapp_business_manage_events` only powers CTWA conversion events;
    a business without it still gets a working AI receptionist."""
    business = _business(db_session)
    provider = _provider(_meta())
    state = _start(db_session, business)

    assert provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    ).success


def test_invalid_token_is_rejected(db_session):
    business = _business(db_session)
    provider = _provider(_meta({"debug_token": _debug_token_payload(is_valid=False)}))
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_TOKEN_EXCHANGE_FAILED


def test_register_failure_stops_before_subscribing(db_session):
    business = _business(db_session)
    calls: list[tuple[str, str]] = []
    provider = _provider(
        _meta({PHONE_NUMBER_ID + "/register": _error(400, code=133006)}, calls=calls)
    )
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_REGISTRATION_FAILED
    assert ("POST", f"{WABA_ID}/subscribed_apps") not in calls
    assert whatsapp_credentials.get_stored_credential(db_session, business.id) is None


def test_pin_mismatch_is_reported_distinctly(db_session):
    """A number carrying a two-step PIN HIRA didn't set needs the owner to
    clear it — different advice from a generic registration failure."""
    business = _business(db_session)
    provider = _provider(_meta({PHONE_NUMBER_ID + "/register": _error(400, code=133005)}))
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_PIN_MISMATCH


def test_subscribe_failure_does_not_persist_a_half_connection(db_session):
    """Without a webhook subscription the number is silently dead, so this
    must not be recorded as connected."""
    business = _business(db_session)
    provider = _provider(_meta({WABA_ID + "/subscribed_apps": _error(400, code=200)}))
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_SUBSCRIPTION_FAILED
    db_session.refresh(business)
    assert business.whatsapp_connection_status == "not_connected"
    assert whatsapp_credentials.get_stored_credential(db_session, business.id) is None


def test_server_errors_are_retried_then_reported_as_transient(db_session):
    business = _business(db_session)
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(503, json={"error": {"code": 1, "type": "TransientError"}})

    provider = MetaEmbeddedSignupProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_META_UNAVAILABLE
    assert attempts["n"] == 3


def test_network_timeout_is_transient(db_session):
    business = _business(db_session)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    provider = MetaEmbeddedSignupProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_META_UNAVAILABLE


def test_client_errors_are_not_retried(db_session):
    business = _business(db_session)
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        return httpx.Response(400, json={"error": {"code": 100}})

    provider = MetaEmbeddedSignupProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    state = _start(db_session, business)

    provider.complete(db_session, business_id=business.id, authorization_code="c", state=state)

    assert attempts["n"] == 1


def test_meta_error_bodies_never_reach_the_client(db_session):
    """Graph error payloads quote back request parameters. The result the
    API serializes must carry a code, not Meta's prose."""
    business = _business(db_session)
    leak = httpx.Response(
        400, json={"error": {"message": "Invalid token EAA-secret-leak", "code": 190}}
    )
    provider = _provider(_meta({"oauth/access_token": leak}))
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert "EAA-secret-leak" not in json.dumps(
        {"success": result.success, "error_code": result.error_code}
    )


# --- WABA / phone number resolution ---------------------------------------


def test_popup_hint_for_an_unauthorized_waba_is_ignored(db_session):
    """The token's granular scopes are authoritative. A hint naming a WABA
    the token doesn't cover must not be honored just because a client said
    so — with one authorized WABA available, that one is used."""
    business = _business(db_session)
    provider = _provider(_meta())
    state = _start(db_session, business)

    result = provider.complete(
        db_session,
        business_id=business.id,
        authorization_code="c",
        state=state,
        waba_id="999999999999999",
    )

    assert result.success is True
    assert result.whatsapp_business_account_id == WABA_ID


def test_ambiguous_waba_without_a_valid_hint_is_refused(db_session):
    business = _business(db_session)
    provider = _provider(
        _meta({"debug_token": _debug_token_payload(waba_ids=(WABA_ID, "444444444444444"))})
    )
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_NO_WABA


def test_token_with_no_authorized_waba_is_refused(db_session):
    business = _business(db_session)
    provider = _provider(_meta({"debug_token": _debug_token_payload(waba_ids=())}))
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_NO_WABA


def test_multiple_phone_numbers_resolve_by_hint(db_session):
    business = _business(db_session)
    second = "555555555555555"
    provider = _provider(
        _meta(
            {
                WABA_ID + "/phone_numbers": _phone_numbers_payload(
                    [(PHONE_NUMBER_ID, DISPLAY_NUMBER), (second, "+1 555 010 0001")]
                ),
                second + "/register": {"success": True},
            }
        )
    )
    state = _start(db_session, business)

    result = provider.complete(
        db_session,
        business_id=business.id,
        authorization_code="c",
        state=state,
        phone_number_id=second,
    )

    assert result.success is True
    assert result.phone_number_id == second
    assert result.display_phone_number == "+1 555 010 0001"


def test_multiple_phone_numbers_without_a_hint_is_refused(db_session):
    business = _business(db_session)
    provider = _provider(
        _meta(
            {
                WABA_ID + "/phone_numbers": _phone_numbers_payload(
                    [(PHONE_NUMBER_ID, DISPLAY_NUMBER), ("555555555555555", "+1 555 010 0001")]
                )
            }
        )
    )
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_NO_PHONE_NUMBER


def test_phone_number_hint_meta_does_not_list_is_refused(db_session):
    business = _business(db_session)
    provider = _provider(_meta())
    state = _start(db_session, business)

    result = provider.complete(
        db_session,
        business_id=business.id,
        authorization_code="c",
        state=state,
        phone_number_id="999999999999999",
    )

    assert result.success is False
    assert result.error_code == ERROR_NO_PHONE_NUMBER


def test_waba_with_no_phone_numbers_is_refused(db_session):
    business = _business(db_session)
    provider = _provider(_meta({WABA_ID + "/phone_numbers": _phone_numbers_payload([])}))
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_NO_PHONE_NUMBER


# --- tenancy, reconnects, idempotency -------------------------------------


def test_phone_number_already_connected_to_another_business_is_refused(db_session):
    """One Meta phone number routes to exactly one business — the webhook
    looks a business up by it, so sharing would silently steal traffic."""
    _business(db_session, name="Incumbent", whatsapp_phone_number_id=PHONE_NUMBER_ID)
    newcomer = _business(db_session, name="Newcomer")
    calls: list[tuple[str, str]] = []
    provider = _provider(_meta(calls=calls))
    state = _start(db_session, newcomer)

    result = provider.complete(
        db_session, business_id=newcomer.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_PHONE_NUMBER_IN_USE
    # Refused before anything was changed on Meta's side.
    assert ("POST", f"{PHONE_NUMBER_ID}/register") not in calls
    assert whatsapp_credentials.get_stored_credential(db_session, newcomer.id) is None


def test_reconnect_reuses_the_existing_pin(db_session):
    """Meta rejects a /register whose PIN doesn't match the one already set
    (133005), so a fresh PIN on reconnect would break every second attempt."""
    business = _business(db_session)
    provider = _provider(_meta())
    first_state = _start(db_session, business)
    provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=first_state
    )
    original_pin = whatsapp_credentials.get_two_factor_pin(
        whatsapp_credentials.get_stored_credential(db_session, business.id)
    )

    sent_pins: list[str] = []
    route = _meta_handler()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/register"):
            sent_pins.append(dict(httpx.QueryParams(request.content.decode()))["pin"])
        return route(request)

    reconnect = MetaEmbeddedSignupProvider(
        client=httpx.Client(transport=httpx.MockTransport(handler))
    )
    second_state = _start(db_session, business)
    result = reconnect.complete(
        db_session, business_id=business.id, authorization_code="c2", state=second_state
    )

    assert result.success is True
    assert sent_pins == [original_pin]
    assert (
        whatsapp_credentials.get_two_factor_pin(
            whatsapp_credentials.get_stored_credential(db_session, business.id)
        )
        == original_pin
    )


def test_reconnect_is_idempotent_and_leaves_one_credential_row(db_session):
    business = _business(db_session)
    provider = _provider(_meta())

    for code in ("c1", "c2", "c3"):
        state = _start(db_session, business)
        assert provider.complete(
            db_session, business_id=business.id, authorization_code=code, state=state
        ).success

    assert (
        db_session.query(WhatsAppCredential)
        .filter(WhatsAppCredential.business_id == business.id)
        .count()
        == 1
    )
    db_session.refresh(business)
    assert business.whatsapp_connection_status == "connected"


def test_reconnecting_the_same_number_to_the_same_business_is_allowed(db_session):
    """The uniqueness guard excludes the business itself — otherwise no
    business could ever reconnect its own number."""
    business = _business(db_session, whatsapp_phone_number_id=PHONE_NUMBER_ID)
    provider = _provider(_meta())
    state = _start(db_session, business)

    assert provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    ).success


def test_a_manual_customer_switching_to_embedded_signup_loses_its_app_secret(db_session):
    """Meta starts signing this business's webhooks with Stoneveil's secret
    at this moment. A stale per-business secret left behind would reject
    every inbound message from here on (Sprint 82's dual-architecture fix)."""
    business = _business(db_session)
    whatsapp_credentials.store_credentials(
        db_session, business.id, access_token="old-token", app_secret="their-own-secret"
    )
    provider = _provider(_meta())
    state = _start(db_session, business)

    assert provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    ).success

    credential = whatsapp_credentials.get_stored_credential(db_session, business.id)
    assert credential.token_source == meta.TOKEN_SOURCE_EMBEDDED_SIGNUP
    assert credential.app_secret_encrypted is None
    assert whatsapp_credentials.get_webhook_signing_secret(credential) == settings.meta_app_secret


# --- deployment configuration --------------------------------------------


def test_provider_refuses_when_tech_provider_config_is_incomplete(db_session, monkeypatch):
    from app.whatsapp.providers.base import EmbeddedSignupNotConfiguredError

    monkeypatch.setattr(settings, "meta_app_secret", "")
    business = _business(db_session)

    with pytest.raises(EmbeddedSignupNotConfiguredError):
        _provider(_meta()).start(db_session, business_id=business.id)


def test_factory_returns_the_real_provider_only_when_configured(monkeypatch):
    from app.whatsapp.providers import get_embedded_signup_provider
    from app.whatsapp.providers.embedded_signup_stub import StubEmbeddedSignupProvider

    assert isinstance(get_embedded_signup_provider(), MetaEmbeddedSignupProvider)

    monkeypatch.setattr(settings, "meta_app_config_id", "")
    assert isinstance(get_embedded_signup_provider(), StubEmbeddedSignupProvider)


# --- the whole point: messages actually arrive afterwards -----------------


def test_webhook_accepts_messages_for_a_business_onboarded_through_embedded_signup(db_session):
    """End to end across both sprints. Onboarding is only real if Meta's
    webhooks are then accepted — and for these customers Meta signs with
    Stoneveil's app secret, which is the exact case that 403'd before
    Sprint 82's dual-architecture fix.
    """
    import hashlib
    import hmac

    from fastapi.testclient import TestClient

    from app.db.session import get_db
    from app.main import app
    from app.webhooks.whatsapp import get_reply_dispatcher

    business = _business(db_session)
    state = _start(db_session, business)
    assert (
        _provider(_meta())
        .complete(db_session, business_id=business.id, authorization_code="c", state=state)
        .success
    )

    dispatched: list[tuple] = []

    def fake_dispatcher():
        def dispatch(background_tasks, conversation_id, message_id, user_text):
            dispatched.append((conversation_id, message_id, user_text))

        return dispatch

    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_reply_dispatcher] = fake_dispatcher
    try:
        body = json.dumps(
            {
                "entry": [
                    {
                        "changes": [
                            {
                                "value": {
                                    "metadata": {"phone_number_id": PHONE_NUMBER_ID},
                                    "contacts": [
                                        {"wa_id": "+15551230000", "profile": {"name": "Test"}}
                                    ],
                                    "messages": [
                                        {
                                            "id": "wamid.es.e2e",
                                            "from": "+15551230000",
                                            "type": "text",
                                            "text": {"body": "are you open?"},
                                        }
                                    ],
                                }
                            }
                        ]
                    }
                ]
            }
        ).encode()
        signature = hmac.new(settings.meta_app_secret.encode(), body, hashlib.sha256).hexdigest()
        resp = TestClient(app).post(
            "/webhooks/whatsapp",
            content=body,
            headers={
                "X-Hub-Signature-256": f"sha256={signature}",
                "Content-Type": "application/json",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert len(dispatched) == 1


# --- Sprint 84: shapes captured from live Meta responses ------------------


def _live_debug_token_payload():
    """Captured verbatim from a real `GET /debug_token` against the
    Stoneveil AI app on 2026-09-20 (token value removed). Note every
    granular scope arrives with **no `target_ids` key** — the shape the
    original implementation assumed would always be present."""
    return {
        "data": {
            "app_id": "898692016617650",
            "type": "SYSTEM_USER",
            "application": "Stoneveil AI",
            "data_access_expires_at": 0,
            "expires_at": 0,
            "is_valid": True,
            "issued_at": 1783184348,
            "scopes": [
                "business_management",
                "whatsapp_business_management",
                "whatsapp_business_messaging",
                "manage_app_solution",
                "whatsapp_business_manage_events",
                "public_profile",
            ],
            "granular_scopes": [
                {"scope": "business_management"},
                {"scope": "whatsapp_business_management"},
                {"scope": "whatsapp_business_messaging"},
                {"scope": "manage_app_solution"},
                {"scope": "whatsapp_business_manage_events"},
            ],
            "user_id": "122105070387377181",
        }
    }


def _live_waba_payload():
    """Captured from a real `GET /{WABA_ID}?fields=id,name,owner_business_info`
    — confirms the field name and that it nests `{name, id}`."""
    return {
        "id": WABA_ID,
        "name": "Test WhatsApp Business Account",
        "owner_business_info": {
            "name": "Stoneveil",
            "id": OWNER_BUSINESS_ID,
            "marketing_messages_onboarding_status": {"status": "NOT_STARTED"},
        },
    }


def _live_phone_numbers_payload():
    """Captured from a real `GET /{WABA_ID}/phone_numbers` — all four
    requested fields exist, and Meta adds a `paging` envelope we ignore."""
    return {
        "data": [
            {
                "id": PHONE_NUMBER_ID,
                "display_phone_number": "+1 555-179-4066",
                "verified_name": "Test Number",
                "code_verification_status": "NOT_VERIFIED",
            }
        ],
        "paging": {"cursors": {"before": "QVFIVHJ", "after": "QVFIVHJ"}},
    }


def test_a_token_whose_granular_scopes_name_no_targets_still_connects(db_session):
    """The bug live validation found. Before Sprint 84 this shape produced
    `no_waba` and every onboarding would have failed at step 3."""
    business = _business(db_session)
    provider = _provider(
        _meta(
            {
                "debug_token": _live_debug_token_payload(),
                WABA_ID: _live_waba_payload(),
                WABA_ID + "/phone_numbers": _live_phone_numbers_payload(),
            }
        )
    )
    state = _start(db_session, business)

    result = provider.complete(
        db_session,
        business_id=business.id,
        authorization_code="c",
        state=state,
        waba_id=WABA_ID,
        phone_number_id=PHONE_NUMBER_ID,
    )

    assert result.success is True
    assert result.whatsapp_business_account_id == WABA_ID
    assert result.display_phone_number == "+1 555-179-4066"
    db_session.refresh(business)
    assert business.meta_business_id == OWNER_BUSINESS_ID


def test_an_unreachable_hinted_waba_is_still_refused(db_session):
    """The fallback relaxes *which call* verifies the id, never whether one
    does. A hint the token can't actually read must still be refused."""
    business = _business(db_session)
    provider = _provider(
        _meta(
            {
                "debug_token": _live_debug_token_payload(),
                "999999999999999": _error(403, code=200),
            }
        )
    )
    state = _start(db_session, business)

    result = provider.complete(
        db_session,
        business_id=business.id,
        authorization_code="c",
        state=state,
        waba_id="999999999999999",
    )

    assert result.success is False
    assert result.error_code == ERROR_NO_WABA


def test_a_hint_outside_named_targets_is_still_refused(db_session):
    """When Meta *does* name targets, they remain authoritative — the
    fallback must not reopen the door the original design closed."""
    business = _business(db_session)
    provider = _provider(_meta({"debug_token": _debug_token_payload(waba_ids=(WABA_ID,))}))
    state = _start(db_session, business)

    result = provider.complete(
        db_session,
        business_id=business.id,
        authorization_code="c",
        state=state,
        waba_id="999999999999999",
    )

    # Falls back to the single authorized WABA, never the unauthorized hint.
    assert result.success is True
    assert result.whatsapp_business_account_id == WABA_ID


def test_no_hint_and_no_named_targets_is_refused(db_session):
    """Nothing to verify means nothing to connect — this must not guess."""
    business = _business(db_session)
    provider = _provider(_meta({"debug_token": _live_debug_token_payload()}))
    state = _start(db_session, business)

    result = provider.complete(
        db_session, business_id=business.id, authorization_code="c", state=state
    )

    assert result.success is False
    assert result.error_code == ERROR_NO_WABA
