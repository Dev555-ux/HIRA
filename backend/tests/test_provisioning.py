"""Unit tests for app.services.provisioning (no HTTP layer)."""

from app.models import Business, User
from app.services.provisioning import get_business_for_clerk_user, provision_business


def test_provision_business_creates_business_and_owner_user(db_session):
    business = provision_business(
        db_session,
        clerk_user_id="clerk_1",
        owner_email="owner@x.com",
        name="Acme",
        industry="Gym",
        contact_email="contact@x.com",
        country="USA",
        timezone="America/New_York",
    )

    assert business.name == "Acme"
    assert business.vertical == "Gym"
    assert business.contact_email == "contact@x.com"
    assert business.country == "USA"
    assert business.timezone == "America/New_York"
    assert business.onboarding_status == "created"
    assert business.whatsapp_connection_status == "not_connected"

    user = db_session.query(User).filter_by(clerk_user_id="clerk_1").one()
    assert user.business_id == business.id
    assert user.role == "owner"


def test_provision_business_defaults_timezone_to_utc(db_session):
    business = provision_business(
        db_session, clerk_user_id="clerk_2", owner_email="owner@x.com", name="Acme"
    )
    assert business.timezone == "UTC"


def test_provision_business_is_idempotent(db_session):
    first = provision_business(
        db_session, clerk_user_id="clerk_3", owner_email="owner@x.com", name="First Name"
    )
    second = provision_business(
        db_session, clerk_user_id="clerk_3", owner_email="owner@x.com", name="Second Name"
    )

    assert first.id == second.id
    assert second.name == "First Name"  # not overwritten by the second call
    assert db_session.query(User).filter_by(clerk_user_id="clerk_3").count() == 1


def test_get_business_for_clerk_user_returns_none_when_unprovisioned(db_session):
    assert get_business_for_clerk_user(db_session, "nobody") is None


def test_provision_business_race_returns_the_winning_business(db_session, monkeypatch):
    """Two concurrent onboarding submissions for the same brand-new Clerk
    identity can both pass the upfront idempotency check before either
    commits. Simulates that by forcing this call's own check to report "not
    provisioned yet" even though another call already committed one — the
    UNIQUE(clerk_user_id) constraint must still be what stops the duplicate
    User row, recovered gracefully (same business returned) rather than
    raising an unhandled IntegrityError."""
    import app.services.provisioning as provisioning_module

    winner = provision_business(
        db_session, clerk_user_id="clerk_race", owner_email="winner@x.com", name="Winner"
    )

    real_lookup = provisioning_module.get_business_for_clerk_user
    calls = {"n": 0}

    def fake_lookup(db, clerk_user_id):
        calls["n"] += 1
        if calls["n"] == 1:
            return None  # the race: this call's own upfront check saw nothing yet
        return real_lookup(db, clerk_user_id)

    monkeypatch.setattr(provisioning_module, "get_business_for_clerk_user", fake_lookup)

    result = provision_business(
        db_session, clerk_user_id="clerk_race", owner_email="loser@x.com", name="Loser"
    )

    assert result.id == winner.id
    assert db_session.query(User).filter_by(clerk_user_id="clerk_race").count() == 1
    assert db_session.query(Business).filter_by(name="Loser").count() == 0
