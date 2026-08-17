"""Shadow Mode — proves WhatsAppProvider's parser matches production on
live traffic, without ever influencing production.

Purpose: PR 3's parity tests already prove `WhatsAppProvider.parse_webhook()`
matches `app/webhooks/whatsapp.py`'s inline parsing on *synthetic* payloads.
Shadow Mode exists to catch the payload shapes our fixtures didn't think of
— by running the new parser against every real webhook a business actually
sends, comparing it against what production really committed, and logging
any divergence. It is purely observational: nothing in this module writes
to the database, enqueues a job, or can change the HTTP response the
webhook already sent.

Comparison strategy (why these fields, not others):

The only ground truth available without an extra database read is
`_persist_inbound`'s own return value — `old_inbound`, a list of
`(conversation_id, message_id, wa_message_id, text)` tuples for whatever it
actually committed. That tuple has no sender/conversation *identity* field
(`conversation_id` is an internal DB UUID, not comparable to anything the
DB-free new parser could ever produce) and nothing for messages it skipped
via dedup — so this module deliberately does NOT compare "sender id" or
"conversation id" against `old_inbound` (there is nothing there to compare
against), and does NOT treat "present in the new parser's output but absent
from `old_inbound`" as a mismatch (see `new_only_ids` below) since the far
more likely explanation is a Meta redelivery `_persist_inbound` correctly
deduped, not a bug. What IS compared, and why each is safe/meaningful
without any additional DB access:

- routing key: `WhatsAppProvider.extract_routing_key()` is called
  independently of the value `receive()` already computed via
  `_first_phone_number_id()` — two separate code paths over the same raw
  bytes, so a mismatch here is a real integration-level signal.
- raw vs. parsed message count: every message object in the payload should
  produce exactly one `NormalizedMessage`, dedup aside — this is the
  cheapest, highest-confidence structural check available (catches the new
  parser silently dropping or duplicating messages, independent of the DB).
- text, per message id present in BOTH `old_inbound` and the new parser's
  output: the one field genuinely comparable between DB-committed data and
  freshly re-parsed data.
- empty sender id: the new parser producing a blank `external_sender_id` is
  a real bug signal on its own, regardless of what `old_inbound` says.
- unsupported message type / media presence: informational bookkeeping
  (today's capabilities() only advertises TEXT, so media should always be
  absent) — not treated as a failure, since a message type HIRA doesn't
  yet handle is expected, not a parser bug.

Nothing here is wired to run synchronously in the request path — see
`run_shadow_comparison()`'s own docstring for why it must only ever be
invoked as a FastAPI BackgroundTask.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from typing import Sequence

from app.channels.base.message import NormalizedMessage
from app.channels.whatsapp.provider import WhatsAppProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TextMismatch:
    """Carries the real message text for in-process use (tests, ad-hoc
    debugging) — `run_shadow_comparison`'s logging never emits `old_text`/
    `new_text` directly; see `_short_fingerprint()`. Do not log this
    dataclass's fields verbatim."""

    external_message_id: str
    old_text: str
    new_text: str


@dataclass(frozen=True)
class ShadowComparisonResult:
    routing_key_old: str
    routing_key_new: str
    raw_message_count: int
    new_parsed_count: int
    old_committed_count: int
    matched_ids: tuple[str, ...]
    new_only_ids: tuple[str, ...]
    old_only_ids: tuple[str, ...]
    text_mismatches: tuple[TextMismatch, ...]
    empty_sender_ids: tuple[str, ...]
    unsupported_type_ids: tuple[str, ...]
    media_present_ids: tuple[str, ...]

    @property
    def routing_key_match(self) -> bool:
        return self.routing_key_old == self.routing_key_new

    @property
    def is_clean(self) -> bool:
        """True only for a genuinely concern-free comparison.
        `new_only_ids` is deliberately excluded — see module docstring —
        so it never flips this to False on its own."""
        return (
            self.routing_key_match
            and self.raw_message_count == self.new_parsed_count
            and not self.old_only_ids
            and not self.text_mismatches
            and not self.empty_sender_ids
            and not self.media_present_ids
        )

    @property
    def has_divergence(self) -> bool:
        """Broader than `not is_clean` — also true when the only thing
        found was expected new_only noise, so that noise still gets logged
        (informationally) even though it doesn't count as a mismatch."""
        return not self.is_clean or bool(self.new_only_ids)


def compare_shadow(
    *,
    payload: dict,
    routing_key_old: str,
    routing_key_new: str,
    old_inbound: Sequence[tuple],
    new_messages: Sequence[NormalizedMessage],
) -> ShadowComparisonResult:
    """Pure function — no I/O, no logging, fully unit-testable on its own.
    `old_inbound` is `_persist_inbound`'s actual return value for this
    webhook call; `new_messages` is `WhatsAppProvider.parse_webhook()`'s
    output for the same raw body."""
    raw_message_count = sum(
        len(change.get("value", {}).get("messages") or [])
        for entry in payload.get("entry", [])
        for change in entry.get("changes", [])
    )

    old_by_id: dict[str, str] = {
        wa_message_id: text for (_conv_id, _msg_id, wa_message_id, text) in old_inbound
    }
    new_by_id: dict[str, NormalizedMessage] = {m.external_message_id: m for m in new_messages}

    common_ids = old_by_id.keys() & new_by_id.keys()
    text_mismatches = tuple(
        sorted(
            (
                TextMismatch(message_id, old_by_id[message_id], new_by_id[message_id].text)
                for message_id in common_ids
                if old_by_id[message_id] != new_by_id[message_id].text
            ),
            key=lambda m: m.external_message_id,
        )
    )
    empty_sender_ids = tuple(
        sorted(mid for mid, m in new_by_id.items() if not m.external_sender_id)
    )
    unsupported_type_ids = tuple(
        sorted(mid for mid, m in new_by_id.items() if m.raw.get("type") not in (None, "text"))
    )
    media_present_ids = tuple(sorted(mid for mid, m in new_by_id.items() if m.media))

    return ShadowComparisonResult(
        routing_key_old=routing_key_old,
        routing_key_new=routing_key_new,
        raw_message_count=raw_message_count,
        new_parsed_count=len(new_messages),
        old_committed_count=len(old_inbound),
        matched_ids=tuple(sorted(common_ids)),
        new_only_ids=tuple(sorted(new_by_id.keys() - old_by_id.keys())),
        old_only_ids=tuple(sorted(old_by_id.keys() - new_by_id.keys())),
        text_mismatches=text_mismatches,
        empty_sender_ids=empty_sender_ids,
        unsupported_type_ids=unsupported_type_ids,
        media_present_ids=media_present_ids,
    )


class ShadowMetrics:
    """Coarse in-process counters — deliberately not thread-safe. This
    runs once per webhook, in a background task, purely for operator
    visibility; an occasional lost increment under concurrent requests is
    an acceptable trade for not adding a lock to a diagnostic-only
    counter. Swap for a real metrics client (statsd/Prometheus) if this
    ever needs to be authoritative — no metrics framework exists in this
    codebase today, and this PR isn't the place to add one."""

    def __init__(self) -> None:
        self.total = 0
        self.matches = 0
        self.mismatches = 0
        self.parser_errors = 0

    def reset(self) -> None:
        self.total = 0
        self.matches = 0
        self.mismatches = 0
        self.parser_errors = 0


_metrics = ShadowMetrics()


def get_shadow_metrics() -> ShadowMetrics:
    """`shadow.total` / `shadow.matches` / `shadow.mismatches` /
    `shadow.parser_errors` as attributes on one object, since there is no
    metrics framework to register named counters with yet."""
    return _metrics


def _short_fingerprint(text: str) -> str:
    """An 8-character content fingerprint — enough to tell "the same
    mismatch happened again" apart from "a different mismatch happened"
    across log lines, without ever putting customer message text in logs."""
    return hashlib.sha256(text.encode()).hexdigest()[:8]


def run_shadow_comparison(
    *,
    raw_body: bytes,
    payload: dict,
    old_inbound: Sequence[tuple],
    routing_key_old: str,
    business_id: uuid.UUID,
) -> None:
    """The only function the webhook route calls. MUST only ever be
    invoked via `BackgroundTasks.add_task()`, never awaited/called inline
    in the request path — the whole point of Shadow Mode is that it can
    never add latency to Meta's webhook ack, which `receive()`'s own
    docstring already treats as a hard requirement for this endpoint.

    Every exception this function or anything it calls can raise is
    caught here and logged; none ever propagate. A background task's
    exception has nowhere to go but a log line anyway (FastAPI does not
    surface it to the client, since the response was already sent) — this
    function's own try/except exists so a Shadow Mode bug shows up as one
    clear `mismatch_category=parser_exception` log line instead of an
    unhandled-exception traceback that looks like a real production
    incident.
    """
    _metrics.total += 1
    try:
        provider = WhatsAppProvider()
        routing_key_new = provider.extract_routing_key(raw_body)
        new_messages = provider.parse_webhook(raw_body)
        result = compare_shadow(
            payload=payload,
            routing_key_old=routing_key_old,
            routing_key_new=routing_key_new,
            old_inbound=old_inbound,
            new_messages=new_messages,
        )
    except Exception as exc:  # noqa: BLE001 — shadow mode must never propagate, by design
        _metrics.parser_errors += 1
        logger.warning(
            "shadow_mode mismatch_category=parser_exception business_id=%s "
            "exception_type=%s exception=%s",
            business_id,
            type(exc).__name__,
            exc,
        )
        return

    if not result.has_divergence:
        _metrics.matches += 1
        return

    if result.is_clean:
        # Only the expected new_only noise — still worth a log line, not a
        # mismatch.
        _metrics.matches += 1
    else:
        _metrics.mismatches += 1
    _log_result(business_id=business_id, result=result)


def _log_result(*, business_id: uuid.UUID, result: ShadowComparisonResult) -> None:
    """Structured, one line per category, every field either an id, a
    count, or a content fingerprint — never raw message text, an access
    token, or anything beyond the identifiers already used for
    operational debugging elsewhere in this codebase (business_id,
    wa_message_id)."""
    if not result.routing_key_match:
        logger.warning(
            "shadow_mode mismatch_category=routing_key business_id=%s old=%s new=%s",
            business_id,
            result.routing_key_old,
            result.routing_key_new,
        )
    if result.raw_message_count != result.new_parsed_count:
        logger.warning(
            "shadow_mode mismatch_category=message_count business_id=%s "
            "routing_key=%s raw_count=%s new_count=%s",
            business_id,
            result.routing_key_new,
            result.raw_message_count,
            result.new_parsed_count,
        )
    for mismatch in result.text_mismatches:
        logger.warning(
            "shadow_mode mismatch_category=text business_id=%s routing_key=%s "
            "wa_message_id=%s old_len=%s new_len=%s old_fp=%s new_fp=%s",
            business_id,
            result.routing_key_new,
            mismatch.external_message_id,
            len(mismatch.old_text),
            len(mismatch.new_text),
            _short_fingerprint(mismatch.old_text),
            _short_fingerprint(mismatch.new_text),
        )
    for message_id in result.empty_sender_ids:
        logger.warning(
            "shadow_mode mismatch_category=empty_sender_id business_id=%s "
            "routing_key=%s wa_message_id=%s",
            business_id,
            result.routing_key_new,
            message_id,
        )
    for message_id in result.old_only_ids:
        logger.warning(
            "shadow_mode mismatch_category=old_only business_id=%s routing_key=%s wa_message_id=%s",
            business_id,
            result.routing_key_new,
            message_id,
        )
    for message_id in result.media_present_ids:
        logger.warning(
            "shadow_mode mismatch_category=unexpected_media business_id=%s "
            "routing_key=%s wa_message_id=%s",
            business_id,
            result.routing_key_new,
            message_id,
        )
    if result.new_only_ids:
        # Informational, not a mismatch category — almost always a Meta
        # redelivery of a message _persist_inbound already committed and
        # therefore correctly deduped; the new parser has no DB to dedupe
        # against, so it (correctly) re-parses it every time. See module
        # docstring.
        logger.info(
            "shadow_mode note=new_only_likely_dedup business_id=%s routing_key=%s wa_message_ids=%s",
            business_id,
            result.routing_key_new,
            ",".join(result.new_only_ids),
        )
