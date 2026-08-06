"""Tests for the onboarding bootstrap service (app/onboarding/)."""

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Business, KbEntry
from app.onboarding import bootstrap, business, knowledge, verification, whatsapp
from tests.conftest import TEST_DATABASE_URL


# --- verification.py ---------------------------------------------------


def test_find_business_by_phone_number_id(db_session):
    biz = Business(name="Clinic A", whatsapp_phone_number_id="PN1")
    db_session.add(biz)
    db_session.flush()

    assert verification.find_business_by_phone_number_id(db_session, "PN1").id == biz.id
    assert verification.find_business_by_phone_number_id(db_session, "missing") is None


def test_find_business_by_any_phone_number_id(db_session):
    biz = Business(name="Clinic A", whatsapp_phone_number_id="NEW")
    db_session.add(biz)
    db_session.flush()

    found = verification.find_business_by_any_phone_number_id(db_session, ["OLD", "NEW"])
    assert found.id == biz.id
    assert verification.find_business_by_any_phone_number_id(db_session, ["OLD", "OTHER"]) is None


def test_resolve_sole_business_ignores_phone_number_id(db_session):
    biz = Business(name="Clinic A", whatsapp_phone_number_id="PN1")
    db_session.add(biz)
    db_session.flush()

    assert verification.resolve_sole_or_by_phone_number_id(db_session, None).id == biz.id


def test_resolve_by_phone_number_id_when_multiple_businesses(db_session):
    db_session.add(Business(name="Clinic A", whatsapp_phone_number_id="PN1"))
    biz_b = Business(name="Clinic B", whatsapp_phone_number_id="PN2")
    db_session.add(biz_b)
    db_session.flush()

    resolved = verification.resolve_sole_or_by_phone_number_id(db_session, "PN2")
    assert resolved.id == biz_b.id


def test_resolve_raises_when_ambiguous(db_session):
    db_session.add(Business(name="Clinic A", whatsapp_phone_number_id="PN1"))
    db_session.add(Business(name="Clinic B", whatsapp_phone_number_id="PN2"))
    db_session.flush()

    with pytest.raises(LookupError, match="Multiple businesses found"):
        verification.resolve_sole_or_by_phone_number_id(db_session, None)


def test_resolve_raises_when_no_business(db_session):
    with pytest.raises(LookupError, match="No business found"):
        verification.resolve_sole_or_by_phone_number_id(db_session, None)


def test_resolve_raises_when_phone_number_id_unmatched(db_session):
    db_session.add(Business(name="Clinic A", whatsapp_phone_number_id="PN1"))
    db_session.add(Business(name="Clinic B", whatsapp_phone_number_id="PN2"))
    db_session.flush()

    with pytest.raises(LookupError, match="No business found with whatsapp_phone_number_id"):
        verification.resolve_sole_or_by_phone_number_id(db_session, "missing")


# --- business.py ---------------------------------------------------------


def test_create_or_update_business_creates(db_session):
    biz, action = business.create_or_update_business(
        db_session, name="Clinic A", phone_number_id="PN1", whatsapp_business_account_id="WABA1"
    )
    assert action == "created"
    assert biz.whatsapp_phone_number_id == "PN1"
    assert biz.mode == "autonomous"


def test_create_or_update_business_updates_without_renaming(db_session):
    business.create_or_update_business(
        db_session,
        name="Original Name",
        phone_number_id="PN1",
        whatsapp_business_account_id="WABA1",
    )
    updated, action = business.create_or_update_business(
        db_session, name="Ignored Name", phone_number_id="PN1", whatsapp_business_account_id="WABA2"
    )
    assert action == "updated"
    assert updated.name == "Original Name"  # matches original script: name isn't touched on update
    assert updated.whatsapp_business_account_id == "WABA2"


# --- whatsapp.py -----------------------------------------------------------


def test_connect_phone_number_repoints_business(db_session):
    biz = Business(name="Clinic A", whatsapp_phone_number_id="OLD")
    db_session.add(biz)
    db_session.commit()

    updated = whatsapp.connect_phone_number(
        db_session,
        old_phone_number_id="OLD",
        new_phone_number_id="NEW",
        whatsapp_business_account_id="WABA1",
    )
    assert updated.id == biz.id
    assert updated.whatsapp_phone_number_id == "NEW"
    assert updated.mode == "autonomous"


def test_connect_phone_number_is_idempotent_after_rotation(db_session):
    biz = Business(name="Clinic A", whatsapp_phone_number_id="OLD")
    db_session.add(biz)
    db_session.commit()
    whatsapp.connect_phone_number(
        db_session,
        old_phone_number_id="OLD",
        new_phone_number_id="NEW",
        whatsapp_business_account_id="WABA1",
    )

    # Re-running after the rotation (only the new id now matches) is a no-op error-free call.
    again = whatsapp.connect_phone_number(
        db_session,
        old_phone_number_id="OLD",
        new_phone_number_id="NEW",
        whatsapp_business_account_id="WABA1",
    )
    assert again.id == biz.id


def test_connect_phone_number_raises_when_no_match(db_session):
    with pytest.raises(LookupError, match="No business found with the old or new phone number id"):
        whatsapp.connect_phone_number(
            db_session,
            old_phone_number_id="OLD",
            new_phone_number_id="NEW",
            whatsapp_business_account_id="WABA1",
        )


# --- knowledge.py ------------------------------------------------------


def test_seed_facts_inserts_and_is_idempotent(db_session, monkeypatch):
    biz = Business(name="Clinic A")
    db_session.add(biz)
    db_session.flush()

    inserted_titles = []

    def fake_index_entry(db, business_id, title, content):
        inserted_titles.append(title)
        entry = KbEntry(
            business_id=business_id, title=title, content=content, embedding=[0.0] * 384
        )
        db.add(entry)
        return [entry]

    monkeypatch.setattr(knowledge, "index_entry", fake_index_entry)

    first_count = knowledge.seed_facts(db_session, biz.id)
    assert first_count == len(knowledge.FACTS)
    assert len(inserted_titles) == len(knowledge.FACTS)

    inserted_titles.clear()
    second_count = knowledge.seed_facts(db_session, biz.id)
    assert second_count == 0
    assert inserted_titles == []

    assert knowledge.count_kb_entries(db_session, biz.id) == len(knowledge.FACTS)


# --- bootstrap.py (session-owning façade) -------------------------------


def test_bootstrap_seed_business_wires_business_module(db_session, monkeypatch):
    # `db_session` only exists here to ensure the (migrated) schema is in
    # place before this test runs; bootstrap.seed_business() opens its own
    # session via the monkeypatched SessionLocal, matching how
    # app.ai.processing is tested (test_orchestrator.py).
    test_sessionmaker = sessionmaker(bind=create_engine(TEST_DATABASE_URL))
    monkeypatch.setattr(bootstrap, "SessionLocal", test_sessionmaker)

    biz, action = bootstrap.seed_business(
        name="Clinic A", phone_number_id="PN1", whatsapp_business_account_id="WABA1"
    )
    assert action == "created"

    with test_sessionmaker() as db:
        found = db.scalars(select(Business).where(Business.id == biz.id)).first()
        assert found is not None
        assert found.whatsapp_phone_number_id == "PN1"
