"""Tests for app/instagram/credentials.py: store/get/disconnect and the
live connection-health check (Sprint 65 PR 2)."""

from __future__ import annotations

import httpx
import pytest
from cryptography.fernet import Fernet

from app.instagram.credentials import (
    CONNECTED,
    INVALID_CREDENTIALS,
    NEEDS_RECONNECT,
    PERMISSION_REVOKED,
    check_connection_health,
    disconnect,
    get_page_access_token,
    get_stored_credential,
    store_credentials,
)
from app.instagram.errors import InstagramAuthError, InstagramDuplicateConnectionError
from app.core.config import settings
from app.models import Business


@pytest.fixture(autouse=True)
def _calendar_key(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())


def _seed_business(db_session, name="A") -> Business:
    biz = Business(name=name)
    db_session.add(biz)
    db_session.commit()
    return biz


def _store(db_session, business_id, *, ig_account_id="ig-1", token="page-token"):
    return store_credentials(
        db_session,
        business_id,
        page_id="page-1",
        page_access_token=token,
        instagram_business_account_id=ig_account_id,
        instagram_username="biz_one",
    )


# --- store / get / disconnect ------------------------------------------------


def test_store_then_get_roundtrips(db_session):
    biz = _seed_business(db_session)
    credential = _store(db_session, biz.id)

    fetched = get_stored_credential(db_session, biz.id)
    assert fetched is not None
    assert fetched.id == credential.id
    assert get_page_access_token(fetched) == "page-token"


def test_store_is_create_or_replace_for_reconnect(db_session):
    biz = _seed_business(db_session)
    first = _store(db_session, biz.id, token="old-token")
    second = _store(db_session, biz.id, token="new-token")

    assert first.id == second.id
    assert get_page_access_token(get_stored_credential(db_session, biz.id)) == "new-token"


def test_store_rejects_ig_account_already_connected_to_another_business(db_session):
    biz_a = _seed_business(db_session, "A")
    biz_b = _seed_business(db_session, "B")
    _store(db_session, biz_a.id, ig_account_id="shared-ig-account")

    with pytest.raises(InstagramDuplicateConnectionError):
        _store(db_session, biz_b.id, ig_account_id="shared-ig-account")

    # The failed attempt must not have left biz_b connected to anything.
    assert get_stored_credential(db_session, biz_b.id) is None


def test_store_credentials_reconnect_race_converges_instead_of_a_false_duplicate_error(
    db_session, monkeypatch
):
    """Sprint 65 PR 7 (production hardening): two concurrent connect/
    reconnect requests for the *same* business (a double-clicked button,
    two open tabs) both hit the business_id unique constraint's IntegrityError
    path — not just the ig_account_id one this module was originally
    hardened for. Before this fix, the loser got a misleading "this account
    is already connected to a different business" error about its own
    business. Simulates the race: a concurrent request commits a row for
    this business, then this call's own stale `get_stored_credential()`
    read (patched to miss it once) forces the INSERT path anyway."""
    biz = _seed_business(db_session)
    _store(db_session, biz.id, ig_account_id="ig-winner", token="token-from-winner")

    import app.instagram.credentials as instagram_credentials_module

    real_get_stored_credential = instagram_credentials_module.get_stored_credential
    calls = {"n": 0}

    def stale_read(db, business_id):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_get_stored_credential(db, business_id)

    monkeypatch.setattr(instagram_credentials_module, "get_stored_credential", stale_read)

    result = _store(db_session, biz.id, ig_account_id="ig-loser", token="token-from-loser")

    assert result.business_id == biz.id
    assert result.instagram_business_account_id == "ig-loser"  # last write wins
    assert get_page_access_token(get_stored_credential(db_session, biz.id)) == "token-from-loser"


def test_disconnect_removes_credential(db_session):
    biz = _seed_business(db_session)
    _store(db_session, biz.id)

    assert disconnect(db_session, biz.id) is True
    assert get_stored_credential(db_session, biz.id) is None


def test_disconnect_returns_false_when_nothing_connected(db_session):
    biz = _seed_business(db_session)
    assert disconnect(db_session, biz.id) is False


# --- connection health check -------------------------------------------------


def _mock_transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_check_connection_health_returns_connected_on_success(db_session):
    biz = _seed_business(db_session)
    credential = _store(db_session, biz.id)

    client = _mock_transport(lambda request: httpx.Response(200, json={"id": "ig-1"}))
    assert check_connection_health(credential, client=client) == CONNECTED


def test_check_connection_health_maps_invalid_token_to_needs_reconnect(db_session):
    biz = _seed_business(db_session)
    credential = _store(db_session, biz.id)

    client = _mock_transport(
        lambda request: httpx.Response(
            400, json={"error": {"code": 190, "message": "Invalid OAuth access token"}}
        )
    )
    assert check_connection_health(credential, client=client) == NEEDS_RECONNECT


def test_check_connection_health_maps_permission_error_to_permission_revoked(db_session):
    biz = _seed_business(db_session)
    credential = _store(db_session, biz.id)

    client = _mock_transport(
        lambda request: httpx.Response(
            403,
            json={"error": {"code": 10, "message": "Permission denied for this action"}},
        )
    )
    assert check_connection_health(credential, client=client) == PERMISSION_REVOKED


def test_check_connection_health_falls_back_to_invalid_credentials_for_unmapped_error(db_session):
    biz = _seed_business(db_session)
    credential = _store(db_session, biz.id)

    client = _mock_transport(
        lambda request: httpx.Response(400, json={"error": {"code": 999, "message": "??"}})
    )
    assert check_connection_health(credential, client=client) == INVALID_CREDENTIALS


def test_check_connection_health_raises_on_network_failure(db_session):
    biz = _seed_business(db_session)
    credential = _store(db_session, biz.id)

    def _raise(request):
        raise httpx.ConnectError("unreachable", request=request)

    client = _mock_transport(_raise)
    with pytest.raises(InstagramAuthError):
        check_connection_health(credential, client=client)
