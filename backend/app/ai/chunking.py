"""Text chunking for knowledge-base ingestion.

Splits a document into retrieval-sized pieces. Strategy: keep paragraphs whole
when they fit; otherwise pack sentences up to a character budget with a small
overlap so context isn't lost at boundaries. A final hard split guards against
a single oversized sentence.

Kept deliberately simple (character-based, no tokenizer dependency) — adequate
for FAQ-style knowledge bases. Can be upgraded to token-aware chunking later
without changing callers.
"""

from __future__ import annotations

import re

DEFAULT_MAX_CHARS = 500
DEFAULT_OVERLAP = 50

_PARAGRAPH_RE = re.compile(r"\n\s*\n")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


def chunk_text(
    text: str, max_chars: int = DEFAULT_MAX_CHARS, overlap: int = DEFAULT_OVERLAP
) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []

    chunks: list[str] = []
    for paragraph in (p.strip() for p in _PARAGRAPH_RE.split(text) if p.strip()):
        if len(paragraph) <= max_chars:
            chunks.append(paragraph)
            continue
        current = ""
        for sentence in _SENTENCE_RE.split(paragraph):
            if current and len(current) + len(sentence) + 1 > max_chars:
                chunks.append(current.strip())
                tail = current[-overlap:] if overlap else ""
                current = f"{tail} {sentence}".strip()
            else:
                current = f"{current} {sentence}".strip() if current else sentence
        if current.strip():
            chunks.append(current.strip())

    return _hard_split_oversized(chunks, max_chars)


def _hard_split_oversized(chunks: list[str], max_chars: int) -> list[str]:
    out: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_chars:
            out.append(chunk)
        else:
            out.extend(chunk[i : i + max_chars] for i in range(0, len(chunk), max_chars))
    return out
