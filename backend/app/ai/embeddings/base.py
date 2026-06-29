"""Embedding provider interface.

All knowledge-base indexing and retrieval depend only on this interface, never
on a concrete provider. That lets us swap the local model for a hosted one
(Voyage, OpenAI) later by adding a class and changing config — no churn in the
KB code. See app/ai/embeddings/__init__.py for the factory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingError(RuntimeError):
    """Raised when an embedding operation fails (model load or inference)."""


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Vector dimension this provider produces (must match the DB column)."""

    @abstractmethod
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed knowledge-base entries for storage."""

    @abstractmethod
    def embed_query(self, text: str) -> list[float]:
        """Embed an incoming question for similarity search."""
