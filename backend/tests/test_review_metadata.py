"""Unit tests for AI review metadata serialization (Sprint: Backend AI Review
Metadata). Covers confidence / grounding / generation_status derivation and
backward compatibility. Pure function over in-memory Message objects — no DB."""

import uuid

from app.api.review_metadata import review_metadata_for
from app.models import Message


def _message(*, direction="outbound", status="pending_approval", ai_meta=None) -> Message:
    return Message(
        id=uuid.uuid4(),
        conversation_id=uuid.uuid4(),
        business_id=uuid.uuid4(),
        direction=direction,
        body="Yes — we're open Saturday.",
        type="text",
        status=status,
        ai_meta=ai_meta,
    )


class TestShape:
    def test_inbound_messages_have_no_review_metadata(self):
        assert review_metadata_for(_message(direction="inbound", status="received")) is None

    def test_outbound_reply_exposes_all_four_fields(self):
        msg = _message(ai_meta={"model": "x", "retrieved_count": 2})
        review = review_metadata_for(msg)
        assert set(review) == {"reply_id", "confidence", "grounding", "generation_status"}
        assert review["reply_id"] == str(msg.id)


class TestConfidence:
    def test_absent_confidence_is_null_not_fabricated(self):
        review = review_metadata_for(_message(ai_meta={"retrieved_count": 3}))
        assert review["confidence"] is None

    def test_real_confidence_passes_through_when_recorded(self):
        review = review_metadata_for(
            _message(ai_meta={"confidence": {"score": 0.91, "level": "high"}})
        )
        assert review["confidence"] == {"score": 0.91, "level": "high"}

    def test_invalid_confidence_level_is_dropped_to_null(self):
        review = review_metadata_for(
            _message(ai_meta={"confidence": {"score": "n/a", "level": "very-high"}})
        )
        assert review["confidence"] == {"score": None, "level": None}


class TestGrounding:
    def test_retrieved_count_is_real_and_exposed(self):
        review = review_metadata_for(_message(ai_meta={"retrieved_count": 4}))
        assert review["grounding"] == {"retrieved_count": 4, "sources": []}

    def test_zero_grounding_is_still_a_structure(self):
        review = review_metadata_for(_message(ai_meta={"retrieved_count": 0}))
        assert review["grounding"]["retrieved_count"] == 0

    def test_no_retrieved_count_means_null_grounding(self):
        review = review_metadata_for(_message(ai_meta={"model": "x"}))
        assert review["grounding"] is None

    def test_sources_pass_through_when_recorded(self):
        review = review_metadata_for(
            _message(
                ai_meta={
                    "retrieved_count": 1,
                    "retrieved_sources": [
                        {"title": "Saturday hours", "type": "kb", "snippet": "9am–2pm"},
                        "garbage-non-dict",
                    ],
                }
            )
        )
        assert review["grounding"]["sources"] == [
            {"title": "Saturday hours", "type": "kb", "snippet": "9am–2pm"}
        ]


class TestGenerationStatus:
    def test_existing_reply_is_complete(self):
        assert (
            review_metadata_for(_message(ai_meta={"retrieved_count": 1}))["generation_status"]
            == "complete"
        )

    def test_honest_fallback_escalation_is_failed(self):
        # app/ai/processing.py::_store_failure_escalation writes an escalated
        # outbound message with no ai_meta — the model produced no reply.
        review = review_metadata_for(_message(status="escalated", ai_meta=None))
        assert review["generation_status"] == "failed"

    def test_generated_reply_with_metadata_stays_complete_even_if_escalated(self):
        # An action failure escalation still had its text generated.
        review = review_metadata_for(
            _message(status="escalated", ai_meta={"retrieved_count": 0, "failure_reason": "x"})
        )
        assert review["generation_status"] == "complete"


class TestBackwardCompatibility:
    def test_empty_ai_meta_never_raises(self):
        for ai_meta in (None, {}):
            review = review_metadata_for(_message(ai_meta=ai_meta))
            assert review["reply_id"]
            assert review["confidence"] is None
            assert review["grounding"] is None
            assert review["generation_status"] in {"complete", "failed"}
