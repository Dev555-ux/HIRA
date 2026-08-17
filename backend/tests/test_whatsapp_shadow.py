"""Sprint 64A PR 4 — Shadow Mode (compare_shadow / run_shadow_comparison).

No database anywhere in this file: `compare_shadow` and
`run_shadow_comparison` are pure/DB-free by contract — they take
already-computed data (a payload dict, `_persist_inbound`'s own return
value, and NormalizedMessages), never a Session. Webhook-route-level
wiring checks (feature flag gating, production continuing when Shadow Mode
fails) live in tests/test_whatsapp_webhook.py instead, since those need the
existing DB-backed webhook fixtures — see that file for the four tests
added alongside this PR.
"""

from __future__ import annotations

import json
import logging
import uuid

import pytest

from app.channels.whatsapp.provider import WhatsAppProvider
from app.channels.whatsapp.shadow import (
    ShadowMetrics,
    compare_shadow,
    get_shadow_metrics,
    run_shadow_comparison,
)

BUSINESS_ID = uuid.uuid4()


def _payload(wa_message_id="wamid.1", from_phone="+15551230000", text="hi", msg_type="text"):
    message: dict = {"id": wa_message_id, "from": from_phone, "type": msg_type}
    if msg_type == "text":
        message["text"] = {"body": text}
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "PN1"},
                            "contacts": [{"wa_id": from_phone, "profile": {"name": "Test"}}],
                            "messages": [message],
                        }
                    }
                ]
            }
        ]
    }


def _old_inbound(wa_message_id="wamid.1", text="hi") -> list[tuple]:
    """Shape-compatible stand-in for `_persist_inbound`'s real return
    value: `(conversation_id, message_id, wa_message_id, text)`."""
    return [(uuid.uuid4(), uuid.uuid4(), wa_message_id, text)]


@pytest.fixture(autouse=True)
def _reset_metrics():
    get_shadow_metrics().reset()
    yield
    get_shadow_metrics().reset()


# --- compare_shadow: identical payloads -------------------------------------


def test_identical_payloads_are_clean_with_no_divergence():
    payload = _payload()
    provider = WhatsAppProvider()
    new_messages = provider.parse_webhook(json.dumps(payload).encode())

    result = compare_shadow(
        payload=payload,
        routing_key_old="PN1",
        routing_key_new="PN1",
        old_inbound=_old_inbound(),
        new_messages=new_messages,
    )

    assert result.is_clean is True
    assert result.has_divergence is False
    assert result.text_mismatches == ()
    assert result.old_only_ids == ()
    assert result.new_only_ids == ()


# --- compare_shadow: parser mismatch ----------------------------------------


def test_text_mismatch_is_detected_and_not_clean():
    payload = _payload(text="hello there")
    provider = WhatsAppProvider()
    new_messages = provider.parse_webhook(json.dumps(payload).encode())

    # old_inbound (what production actually committed) disagrees with what
    # the payload/new parser say the text is — simulates a real divergence.
    result = compare_shadow(
        payload=payload,
        routing_key_old="PN1",
        routing_key_new="PN1",
        old_inbound=_old_inbound(text="a different message"),
        new_messages=new_messages,
    )

    assert result.is_clean is False
    assert len(result.text_mismatches) == 1
    mismatch = result.text_mismatches[0]
    assert mismatch.external_message_id == "wamid.1"
    assert mismatch.old_text == "a different message"
    assert mismatch.new_text == "hello there"


def test_routing_key_mismatch_is_detected():
    payload = _payload()
    provider = WhatsAppProvider()
    new_messages = provider.parse_webhook(json.dumps(payload).encode())

    result = compare_shadow(
        payload=payload,
        routing_key_old="PN1",
        routing_key_new="PN_DIFFERENT",
        old_inbound=_old_inbound(),
        new_messages=new_messages,
    )

    assert result.routing_key_match is False
    assert result.is_clean is False


def test_old_only_message_is_a_real_mismatch():
    """Old committed a message the new parser produced nothing for —
    unlike new_only, this is never expected/benign."""
    payload = _payload(wa_message_id="wamid.new")
    provider = WhatsAppProvider()
    new_messages = provider.parse_webhook(json.dumps(payload).encode())

    result = compare_shadow(
        payload=payload,
        routing_key_old="PN1",
        routing_key_new="PN1",
        old_inbound=_old_inbound(wa_message_id="wamid.old-only"),
        new_messages=new_messages,
    )

    assert result.old_only_ids == ("wamid.old-only",)
    assert result.is_clean is False


def test_new_only_message_does_not_count_as_a_mismatch():
    """New parser produced a message old_inbound doesn't have — the
    expected shape of a Meta redelivery `_persist_inbound` correctly
    deduped. Should not flip is_clean, but should still be visible."""
    payload = _payload(wa_message_id="wamid.redelivered")
    provider = WhatsAppProvider()
    new_messages = provider.parse_webhook(json.dumps(payload).encode())

    result = compare_shadow(
        payload=payload,
        routing_key_old="PN1",
        routing_key_new="PN1",
        old_inbound=[],  # nothing committed: old deduped this message away
        new_messages=new_messages,
    )

    assert result.new_only_ids == ("wamid.redelivered",)
    assert result.is_clean is True
    assert result.has_divergence is True


# --- compare_shadow: unsupported message type -------------------------------


def test_unsupported_message_type_is_informational_not_a_mismatch():
    payload = _payload(msg_type="image", wa_message_id="wamid.img")
    provider = WhatsAppProvider()
    new_messages = provider.parse_webhook(json.dumps(payload).encode())

    result = compare_shadow(
        payload=payload,
        routing_key_old="PN1",
        routing_key_new="PN1",
        old_inbound=_old_inbound(wa_message_id="wamid.img", text=""),  # empty body, same as new
        new_messages=new_messages,
    )

    assert result.unsupported_type_ids == ("wamid.img",)
    assert result.is_clean is True  # an unhandled type isn't a parser bug


# --- run_shadow_comparison: parser exception --------------------------------


def test_parser_exception_is_caught_logged_and_never_raises(monkeypatch, caplog):
    def _boom(self, raw_body: bytes):
        raise RuntimeError("simulated parser failure")

    monkeypatch.setattr(WhatsAppProvider, "parse_webhook", _boom)

    with caplog.at_level(logging.WARNING):
        run_shadow_comparison(
            raw_body=json.dumps(_payload()).encode(),
            payload=_payload(),
            old_inbound=_old_inbound(),
            routing_key_old="PN1",
            business_id=BUSINESS_ID,
        )  # must not raise

    assert get_shadow_metrics().parser_errors == 1
    assert get_shadow_metrics().mismatches == 0
    assert any("mismatch_category=parser_exception" in r.message for r in caplog.records)


# --- run_shadow_comparison: logging only on mismatch ------------------------


def test_no_log_lines_emitted_for_a_clean_comparison(caplog):
    with caplog.at_level(logging.INFO):
        run_shadow_comparison(
            raw_body=json.dumps(_payload()).encode(),
            payload=_payload(),
            old_inbound=_old_inbound(),
            routing_key_old="PN1",
            business_id=BUSINESS_ID,
        )

    shadow_records = [r for r in caplog.records if r.name == "app.channels.whatsapp.shadow"]
    assert shadow_records == []
    assert get_shadow_metrics().matches == 1
    assert get_shadow_metrics().mismatches == 0


def test_log_line_emitted_only_when_mismatch_exists(caplog):
    payload = _payload(text="hello there")
    with caplog.at_level(logging.WARNING):
        run_shadow_comparison(
            raw_body=json.dumps(payload).encode(),
            payload=payload,
            old_inbound=_old_inbound(text="a different message"),
            routing_key_old="PN1",
            business_id=BUSINESS_ID,
        )

    assert get_shadow_metrics().mismatches == 1
    text_mismatch_logs = [r for r in caplog.records if "mismatch_category=text" in r.message]
    assert len(text_mismatch_logs) == 1
    # Never log raw customer message content.
    log_line = text_mismatch_logs[0].message
    assert "hello there" not in log_line
    assert "a different message" not in log_line
    assert "old_fp=" in log_line and "new_fp=" in log_line


def test_metrics_counters_are_independent_and_resettable():
    metrics = get_shadow_metrics()
    assert isinstance(metrics, ShadowMetrics)
    assert (metrics.total, metrics.matches, metrics.mismatches, metrics.parser_errors) == (
        0,
        0,
        0,
        0,
    )

    run_shadow_comparison(
        raw_body=json.dumps(_payload()).encode(),
        payload=_payload(),
        old_inbound=_old_inbound(),
        routing_key_old="PN1",
        business_id=BUSINESS_ID,
    )
    assert metrics.total == 1
    assert metrics.matches == 1

    metrics.reset()
    assert metrics.total == 0
