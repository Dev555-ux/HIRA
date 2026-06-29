"""Local embedding provider backed by BAAI/bge-small-en-v1.5 via fastembed.

Runs entirely on-device (ONNX, no PyTorch, no API key, no per-call cost). The
model is loaded lazily on first use and reused. Loading downloads the model the
first time, so load is retried with backoff; inference is local and not retried.
"""

from __future__ import annotations

import logging
import time

from app.ai.embeddings.base import EmbeddingError, EmbeddingProvider

logger = logging.getLogger(__name__)

# BAAI/bge-small-en-v1.5 produces 384-dimensional vectors. This must match the
# kb_entries.embedding column type; changing models with a different dimension
# requires a migration.
BGE_SMALL_DIMENSION = 384

# bge models recommend prefixing the query (not the documents) for retrieval.
_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class LocalBGEProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", *, load_attempts: int = 3):
        self._model_name = model_name
        self._load_attempts = load_attempts
        self._model = None  # lazy

    @property
    def dimension(self) -> int:
        return BGE_SMALL_DIMENSION

    def _ensure_model(self):
        if self._model is not None:
            return self._model
        from fastembed import TextEmbedding  # imported lazily to keep startup fast

        last_error: Exception | None = None
        for attempt in range(1, self._load_attempts + 1):
            try:
                logger.info("Loading embedding model %s (attempt %d)", self._model_name, attempt)
                self._model = TextEmbedding(self._model_name)
                return self._model
            except Exception as exc:  # model download/init may fail transiently
                last_error = exc
                logger.warning("Embedding model load failed (attempt %d): %s", attempt, exc)
                if attempt < self._load_attempts:
                    time.sleep(0.5 * attempt)
        raise EmbeddingError(f"Could not load embedding model {self._model_name}: {last_error}")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        model = self._ensure_model()
        try:
            return [vec.tolist() for vec in model.embed(texts)]
        except Exception as exc:
            raise EmbeddingError(f"Failed to embed documents: {exc}") from exc

    def embed_query(self, text: str) -> list[float]:
        model = self._ensure_model()
        try:
            return next(iter(model.embed([_QUERY_PREFIX + text]))).tolist()
        except Exception as exc:
            raise EmbeddingError(f"Failed to embed query: {exc}") from exc
