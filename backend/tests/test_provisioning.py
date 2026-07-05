"""Unit tests for app.services.provisioning (no HTTP layer)."""

from app.models import User
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
