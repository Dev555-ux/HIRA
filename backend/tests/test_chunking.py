"""Tests for knowledge-base text chunking."""

from app.ai.chunking import chunk_text


def test_empty_text_returns_no_chunks():
    assert chunk_text("") == []
    assert chunk_text("   ") == []


def test_short_text_is_one_chunk():
    assert chunk_text("We are open 9am to 5pm.") == ["We are open 9am to 5pm."]


def test_paragraphs_kept_whole_when_small():
    text = "First paragraph.\n\nSecond paragraph."
    assert chunk_text(text) == ["First paragraph.", "Second paragraph."]


def test_long_paragraph_is_split_under_budget():
    sentence = "This clinic offers many services. "
    chunks = chunk_text(sentence * 60, max_chars=200, overlap=20)
    assert len(chunks) > 1
    assert all(len(c) <= 200 for c in chunks)


def test_oversized_single_sentence_is_hard_split():
    chunks = chunk_text("x" * 1200, max_chars=500)
    assert all(len(c) <= 500 for c in chunks)
    assert "".join(chunks) == "x" * 1200
