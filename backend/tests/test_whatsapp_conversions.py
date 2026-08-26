"""Tests for the Meta Conversions API for Business Messaging (Sprint 73):
`LeadSubmitted` for leads that originated from a Click-to-WhatsApp ad.

Covers the whole path end to end against a mocked Graph transport — click-id
capture in the webhook parser, its one-time persistence on the Conversation,
the enqueue-on-qualify trigger and its idempotency, and the two Graph calls
themselves. No live Meta call is made or simulated as made; see
documentation/WHATSAPP_INTEGRATION.md for the deferred live-verification
status.
"""

import json
import uuid

import httpx
import pytest
from cryptography.fernet import Fernet

from app.channels.base.message import NormalizedMessage
from app.channels.whatsapp.parsing import parse_messages
from app.core.config import settings
from app.jobs.handlers import PermanentJobError, TransientJobError, get_handler
from app.jobs.models import JobOutbox
from app.models import Business, Conversation, Customer, Lead
from app.services.leads import create_lead, update_lead
from app.services.messaging_service import MessagingService
from app.whatsapp.conversion_tasks import (
    NOT_ATTRIBUTABLE,
    SEND_LEAD_SUBMITTED_TASK,
    enqueue_lead_submitted,
    ensure_registered,
    handle_send_lead_submitted,
)
from app.whatsapp.conversions import (
    ConversionEventError,
    resolve_dataset_id,
    send_conversion_event,
)
from app.whatsapp.credentials import store_credentials

CLID = "ARAaZ_fake_looking_but_only_ever_supplied_by_meta"


@pytest.fixture(autouse=True)
def _encryption_key(monkeypatch):
    monkeypatch.setattr(settings, "calendar_encryption_key", Fernet.generate_key().decode())


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def _business(db, *, waba="WABA1", dataset=None):
    biz = Business(
        name="Clinic A",
        whatsapp_phone_number_id=f"PN-{uuid.uuid4().hex[:8]}",
        whatsapp_business_account_id=waba,
        whatsapp_dataset_id=dataset,
    )
    db.add(biz)
    db.flush()
    return biz


def _customer(db, business_id, phone="+15551230000"):
    customer = Customer(business_id=business_id, wa_phone=phone)
    db.add(customer)
    db.flush()
    return customer


def _conversation(db, business_id, customer_id, *, ctwa_clid=None):
    conversation = Conversation(
        business_id=business_id, customer_id=customer_id, ctwa_clid=ctwa_clid
    )
    db.add(conversation)
    db.flush()
    return conversation


# --- parsing: lifting referral.ctwa_clid off the webhook payload -------------


def test_parse_messages_lifts_ctwa_clid_from_the_referral_object():
    messages = [
        {
            "id": "wamid.1",
            "from": "15551230000",
            "type": "text",
            "text": {"body": "hi"},
            "referral": {"source_type": "ad", "source_id": "1234", "ctwa_clid": CLID},
        }
    ]

    [parsed] = parse_messages(messages, [])

    assert parsed.ctwa_clid == CLID


def test_parse_messages_leaves_ctwa_clid_none_without_a_referral():
    messages = [{"id": "wamid.1", "from": "15551230000", "type": "text", "text": {"body": "hi"}}]

    [parsed] = parse_messages(messages, [])

    assert parsed.ctwa_clid is None


def test_parse_messages_treats_a_blank_ctwa_clid_as_absent():
    messages = [
        {
            "id": "wamid.1",
            "from": "15551230000",
            "type": "text",
            "text": {"body": "hi"},
            "referral": {"source_type": "ad", "ctwa_clid": ""},
        }
    ]

    [parsed] = parse_messages(messages, [])

    assert parsed.ctwa_clid is None


# --- persistence: written once, never overwritten ----------------------------


def _inbound(wa_id, text="hi", ctwa_clid=None):
    return NormalizedMessage(
        channel="whatsapp",
        external_conversation_id="15551230000",
        external_message_id=wa_id,
        external_sender_id="15551230000",
        text=text,
        ctwa_clid=ctwa_clid,
        raw={"type": "text"},
    )


def test_record_inbound_stores_the_click_id_on_the_conversation(db_session):
    biz = _business(db_session)

    MessagingService(db_session).record_inbound(biz.id, [_inbound("wamid.1", ctwa_clid=CLID)])

    conversation = db_session.query(Conversation).filter_by(business_id=biz.id).one()
    assert conversation.ctwa_clid == CLID


def test_record_inbound_does_not_overwrite_an_existing_click_id(db_session):
    biz = _business(db_session)
    service = MessagingService(db_session)
    service.record_inbound(biz.id, [_inbound("wamid.1", ctwa_clid=CLID)])

    # A later message in the same thread carries no referral at all; a second
    # ad click would carry a different one. Neither may replace the click that
    # actually opened this conversation.
    service.record_inbound(biz.id, [_inbound("wamid.2")])
    service.record_inbound(biz.id, [_inbound("wamid.3", ctwa_clid="a-later-click")])

    conversation = db_session.query(Conversation).filter_by(business_id=biz.id).one()
    assert conversation.ctwa_clid == CLID


def test_record_inbound_leaves_click_id_null_for_organic_conversations(db_session):
    biz = _business(db_session)

    MessagingService(db_session).record_inbound(biz.id, [_inbound("wamid.1")])

    conversation = db_session.query(Conversation).filter_by(business_id=biz.id).one()
    assert conversation.ctwa_clid is None


# --- trigger: enqueue on stage -> qualified ----------------------------------


def _qualifiable_lead(db, *, ctwa_clid=None):
    biz = _business(db)
    customer = _customer(db, biz.id)
    _conversation(db, biz.id, customer.id, ctwa_clid=ctwa_clid)
    lead = create_lead(db, biz.id, customer.id, stage="contacted")
    return biz, lead


def _jobs(db, business_id):
    return (
        db.query(JobOutbox)
        .filter(
            JobOutbox.business_id == business_id, JobOutbox.task_name == SEND_LEAD_SUBMITTED_TASK
        )
        .all()
    )


def test_qualifying_an_ad_originated_lead_enqueues_one_event(db_session):
    biz, lead = _qualifiable_lead(db_session, ctwa_clid=CLID)

    update_lead(db_session, biz.id, lead.id, {"stage": "qualified"})

    [job] = _jobs(db_session, biz.id)
    assert job.payload == {"lead_id": str(lead.id)}
    assert job.idempotency_key == f"ctwa_lead_submitted:{lead.id}"


def test_qualifying_a_lead_with_no_click_id_sends_and_queues_nothing(db_session):
    biz, lead = _qualifiable_lead(db_session)

    update_lead(db_session, biz.id, lead.id, {"stage": "qualified"})

    assert _jobs(db_session, biz.id) == []


def test_enqueue_returns_the_not_attributable_state_without_a_click_id(db_session):
    _biz, lead = _qualifiable_lead(db_session)

    assert enqueue_lead_submitted(db_session, lead) == NOT_ATTRIBUTABLE


def test_enqueue_returns_none_when_the_event_is_queued(db_session):
    _biz, lead = _qualifiable_lead(db_session, ctwa_clid=CLID)

    assert enqueue_lead_submitted(db_session, lead) is None


def test_requalifying_a_lead_never_produces_a_second_event(db_session):
    biz, lead = _qualifiable_lead(db_session, ctwa_clid=CLID)

    update_lead(db_session, biz.id, lead.id, {"stage": "qualified"})
    update_lead(db_session, biz.id, lead.id, {"stage": "contacted"})
    update_lead(db_session, biz.id, lead.id, {"stage": "qualified"})

    assert len(_jobs(db_session, biz.id)) == 1


def test_other_stage_transitions_do_not_enqueue_anything(db_session):
    biz, lead = _qualifiable_lead(db_session, ctwa_clid=CLID)

    for stage in ("proposal_sent", "negotiation", "won", "lost"):
        update_lead(db_session, biz.id, lead.id, {"stage": stage})

    assert _jobs(db_session, biz.id) == []


def test_a_non_stage_update_does_not_enqueue_anything(db_session):
    biz, lead = _qualifiable_lead(db_session, ctwa_clid=CLID)
    update_lead(db_session, biz.id, lead.id, {"stage": "qualified"})

    update_lead(db_session, biz.id, lead.id, {"notes": "spoke to them again"})

    assert len(_jobs(db_session, biz.id)) == 1


def test_the_lead_stage_change_still_commits_normally(db_session):
    biz, lead = _qualifiable_lead(db_session, ctwa_clid=CLID)

    update_lead(db_session, biz.id, lead.id, {"stage": "qualified"})

    assert db_session.get(Lead, lead.id).stage == "qualified"


# --- transport: GET /{WABA_ID}/dataset ---------------------------------------


def test_resolve_dataset_id_returns_metas_dataset():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/WABA1/dataset")
        assert request.headers["Authorization"] == "Bearer tok"
        return httpx.Response(200, json={"data": [{"id": "DS1"}]})

    assert resolve_dataset_id("WABA1", "tok", client=_client(handler)) == "DS1"


def test_resolve_dataset_id_refuses_to_invent_one_when_meta_returns_none():
    def handler(request):
        return httpx.Response(200, json={"data": []})

    with pytest.raises(ConversionEventError) as exc:
        resolve_dataset_id("WABA1", "tok", client=_client(handler))
    assert exc.value.retryable is False


def test_resolve_dataset_id_treats_4xx_as_permanent():
    def handler(request):
        return httpx.Response(403, text="permission denied")

    with pytest.raises(ConversionEventError) as exc:
        resolve_dataset_id("WABA1", "tok", client=_client(handler))
    assert exc.value.retryable is False


def test_resolve_dataset_id_treats_5xx_as_retryable():
    def handler(request):
        return httpx.Response(503)

    with pytest.raises(ConversionEventError) as exc:
        resolve_dataset_id("WABA1", "tok", client=_client(handler))
    assert exc.value.retryable is True


# --- transport: POST /{DATASET_ID}/events ------------------------------------


def test_send_conversion_event_posts_metas_documented_payload():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers["Authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"events_received": 1})

    send_conversion_event(
        "DS1",
        "tok",
        event_name="LeadSubmitted",
        whatsapp_business_account_id="WABA1",
        ctwa_clid=CLID,
        event_time=1675999999,
        client=_client(handler),
    )

    assert seen["path"].endswith(f"/{settings.whatsapp_graph_version}/DS1/events")
    assert seen["auth"] == "Bearer tok"
    assert seen["body"] == {
        "data": [
            {
                "event_name": "LeadSubmitted",
                "event_time": 1675999999,
                "action_source": "business_messaging",
                "messaging_channel": "whatsapp",
                "user_data": {
                    "whatsapp_business_account_id": "WABA1",
                    "ctwa_clid": CLID,
                },
            }
        ],
        "partner_agent": "hira",
    }


def test_send_conversion_event_refuses_an_empty_click_id():
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("Meta must not be called without a ctwa_clid")

    with pytest.raises(ConversionEventError):
        send_conversion_event(
            "DS1",
            "tok",
            event_name="LeadSubmitted",
            whatsapp_business_account_id="WABA1",
            ctwa_clid="",
            event_time=1,
            client=_client(handler),
        )


def test_send_conversion_event_treats_4xx_as_permanent():
    def handler(request):
        return httpx.Response(400, text="bad dataset")

    with pytest.raises(ConversionEventError) as exc:
        send_conversion_event(
            "DS1",
            "tok",
            event_name="LeadSubmitted",
            whatsapp_business_account_id="WABA1",
            ctwa_clid=CLID,
            event_time=1,
            client=_client(handler),
        )
    assert exc.value.retryable is False


def test_send_conversion_event_treats_a_transport_failure_as_retryable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route to host")

    with pytest.raises(ConversionEventError) as exc:
        send_conversion_event(
            "DS1",
            "tok",
            event_name="LeadSubmitted",
            whatsapp_business_account_id="WABA1",
            ctwa_clid=CLID,
            event_time=1,
            client=_client(handler),
        )
    assert exc.value.retryable is True


# --- handler: the job the worker actually runs -------------------------------


def _job_for(db, lead):
    return JobOutbox(
        business_id=lead.business_id,
        task_name=SEND_LEAD_SUBMITTED_TASK,
        payload={"lead_id": str(lead.id)},
    )


def _connected(db, *, dataset=None, ctwa_clid=CLID):
    biz = _business(db, dataset=dataset)
    customer = _customer(db, biz.id)
    _conversation(db, biz.id, customer.id, ctwa_clid=ctwa_clid)
    store_credentials(db, biz.id, access_token="tok", app_secret="sec")
    lead = create_lead(db, biz.id, customer.id, stage="qualified")
    return biz, lead


def test_handler_looks_up_the_dataset_once_and_caches_it(db_session, monkeypatch):
    biz, lead = _connected(db_session)
    calls = []

    monkeypatch.setattr(
        "app.whatsapp.conversion_tasks.resolve_dataset_id",
        lambda waba, token: calls.append(("resolve", waba, token)) or "DS1",
    )
    monkeypatch.setattr(
        "app.whatsapp.conversion_tasks.send_conversion_event",
        lambda dataset, token, **kw: calls.append(("send", dataset, kw)),
    )

    handle_send_lead_submitted(db_session, _job_for(db_session, lead))

    assert calls[0] == ("resolve", "WABA1", "tok")
    assert db_session.get(Business, biz.id).whatsapp_dataset_id == "DS1"
    assert calls[1][0] == "send" and calls[1][1] == "DS1"
    assert calls[1][2]["event_name"] == "LeadSubmitted"
    assert calls[1][2]["ctwa_clid"] == CLID


def test_handler_skips_the_lookup_when_the_dataset_is_already_cached(db_session, monkeypatch):
    _biz, lead = _connected(db_session, dataset="DS-CACHED")

    def _boom(*args, **kwargs):  # pragma: no cover
        raise AssertionError("dataset already known; must not be looked up again")

    monkeypatch.setattr("app.whatsapp.conversion_tasks.resolve_dataset_id", _boom)
    sent = {}
    monkeypatch.setattr(
        "app.whatsapp.conversion_tasks.send_conversion_event",
        lambda dataset, token, **kw: sent.update(dataset=dataset),
    )

    handle_send_lead_submitted(db_session, _job_for(db_session, lead))

    assert sent["dataset"] == "DS-CACHED"


def test_handler_maps_a_retryable_meta_failure_onto_a_transient_job_error(db_session, monkeypatch):
    _biz, lead = _connected(db_session, dataset="DS1")
    monkeypatch.setattr(
        "app.whatsapp.conversion_tasks.send_conversion_event",
        lambda *a, **k: (_ for _ in ()).throw(ConversionEventError("503", retryable=True)),
    )

    with pytest.raises(TransientJobError):
        handle_send_lead_submitted(db_session, _job_for(db_session, lead))


def test_handler_maps_a_permanent_meta_failure_onto_a_permanent_job_error(db_session, monkeypatch):
    _biz, lead = _connected(db_session, dataset="DS1")
    monkeypatch.setattr(
        "app.whatsapp.conversion_tasks.send_conversion_event",
        lambda *a, **k: (_ for _ in ()).throw(ConversionEventError("400", retryable=False)),
    )

    with pytest.raises(PermanentJobError):
        handle_send_lead_submitted(db_session, _job_for(db_session, lead))


def test_handler_fails_permanently_without_stored_credentials(db_session, monkeypatch):
    biz = _business(db_session, dataset="DS1")
    customer = _customer(db_session, biz.id)
    _conversation(db_session, biz.id, customer.id, ctwa_clid=CLID)
    lead = create_lead(db_session, biz.id, customer.id, stage="qualified")

    def _boom(*args, **kwargs):  # pragma: no cover
        raise AssertionError("Meta must not be called without credentials")

    monkeypatch.setattr("app.whatsapp.conversion_tasks.send_conversion_event", _boom)

    with pytest.raises(PermanentJobError):
        handle_send_lead_submitted(db_session, _job_for(db_session, lead))


def test_handler_fails_permanently_when_the_click_id_is_gone(db_session, monkeypatch):
    _biz, lead = _connected(db_session, dataset="DS1", ctwa_clid=None)

    def _boom(*args, **kwargs):  # pragma: no cover
        raise AssertionError("Meta must not be called without a ctwa_clid")

    monkeypatch.setattr("app.whatsapp.conversion_tasks.send_conversion_event", _boom)

    with pytest.raises(PermanentJobError):
        handle_send_lead_submitted(db_session, _job_for(db_session, lead))


def test_handler_is_registered_for_the_worker_to_find():
    # ensure_registered() is idempotent and re-runnable by contract; called
    # here because tests/jobs/test_worker.py clears the global registry and
    # does not restore it, so import-time registration cannot be relied on
    # once that module has run in the same session.
    ensure_registered()

    assert get_handler(SEND_LEAD_SUBMITTED_TASK) is handle_send_lead_submitted
