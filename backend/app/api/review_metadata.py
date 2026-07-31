"""Review metadata for AI-generated replies (Sprint: Backend AI Review Metadata).

One place that derives the review fields the Inbox's ReviewReplyCard consumes —
`reply_id`, `confidence`, `grounding`, `generation_status` — from what the
backend *actually* records on a Message. Shared by both message payloads (the
conversation thread in app/api/conversations.py and the /pending list in
app/api/dashboard.py) so the contract can't drift between them.

Guiding rule (from the sprint brief): expose real data only, `null` otherwise —
never fabricate a value. Each field below is also forward-compatible: the moment
the AI pipeline persists a real confidence score or the retrieved sources into
`Message.ai_meta`, it flows through here with no serializer change.
"""

from __future__ import annotations

from typing import Any

from app.models import Message

_CONFIDENCE_LEVELS = {"high", "medium", "low"}


def review_metadata_for(message: Message) -> dict | None:
    """Review metadata for one message, or None for inbound (customer) messages,
    which carry no AI review data."""
    if message.direction != "outbound":
        return None
    ai_meta: dict[str, Any] = message.ai_meta or {}
    return {
        "reply_id": str(message.id),
        "confidence": _confidence(ai_meta),
        "grounding": _grounding(ai_meta),
        "generation_status": _generation_status(message, ai_meta),
    }


def _confidence(ai_meta: dict[str, Any]) -> dict | None:
    """Real confidence, or None.

    Today the AI pipeline (app/ai/orchestrator.py, app/ai/intent.py) computes no
    confidence score — intent classification is deterministic keyword matching,
    not probabilistic — so this is None for every reply. It is NOT fabricated
    from a proxy (e.g. grounding count). Wired to read `ai_meta["confidence"]`
    so it lights up automatically once the pipeline records a real score."""
    raw = ai_meta.get("confidence")
    if not isinstance(raw, dict):
        return None
    score = raw.get("score")
    level = raw.get("level")
    return {
        "score": float(score) if isinstance(score, (int, float)) else None,
        "level": level if level in _CONFIDENCE_LEVELS else None,
    }


def _grounding(ai_meta: dict[str, Any]) -> dict | None:
    """Real grounding, or None.

    `retrieved_count` is genuinely recorded on every AI reply (see
    app/ai/processing.py). The retrieved *sources* (title/type/snippet) are not
    persisted per-message today, so `sources` is empty until the pipeline stores
    `ai_meta["retrieved_sources"]` — at which point they pass straight through."""
    count = ai_meta.get("retrieved_count")
    if not isinstance(count, int):
        return None
    sources = ai_meta.get("retrieved_sources")
    return {
        "retrieved_count": count,
        "sources": _sources(sources),
    }


def _sources(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "title": item.get("title"),
                "type": item.get("type"),
                "snippet": item.get("snippet"),
            }
        )
    return out


def _generation_status(message: Message, ai_meta: dict[str, Any]) -> str:
    """Real generation state for a persisted reply: "complete" or "failed".

    The message existing means generation finished, so the normal case is
    "complete". The one genuine generation failure is the honest-fallback
    escalation (app/ai/processing.py::_store_failure_escalation), written with
    status="escalated" and no ai_meta because the model could not produce a
    reply at all → "failed".

    The transient "idle"/"working" states of the enum are deliberately not
    emitted here: they describe a conversation *before* a reply row exists (the
    generate_ai_reply outbox job in flight), which no persisted Message can
    carry. Exposing them would require a separate conversation-level signal —
    see the deliverable notes."""
    if message.status == "escalated" and not ai_meta:
        return "failed"
    return "complete"
