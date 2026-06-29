"""Embedding provider factory.

`get_embedding_provider()` returns the configured provider (default: local BGE).
The instance is cached so the model loads once per process.

To add a provider later (e.g. Voyage, OpenAI):
1. Create a class implementing `EmbeddingProvider` in this package.
2. Register it in the `_PROVIDERS` map below.
3. Set `EMBEDDING_PROVIDER=<name>` in the environment.
No knowledge-base code needs to change.
"""

from __future__ import annotations

from functools import lru_cache

from app.ai.embeddings.base import EmbeddingError, EmbeddingProvider
from app.ai.embeddings.local_bge import LocalBGEProvider
from app.core.config import settings

_PROVIDERS = {
    "local_bge": lambda: LocalBGEProvider(settings.embedding_model),
    # "voyage": lambda: VoyageProvider(settings.voyage_api_key, settings.embedding_model),
    # "openai": lambda: OpenAIEmbeddingProvider(settings.openai_api_key, settings.embedding_model),
}


@lru_cache(maxsize=None)
def get_embedding_provider(name: str | None = None) -> EmbeddingProvider:
    name = name or settings.embedding_provider
    factory = _PROVIDERS.get(name)
    if factory is None:
        raise EmbeddingError(f"Unknown embedding provider '{name}'. Known: {sorted(_PROVIDERS)}")
    return factory()


__all__ = ["EmbeddingProvider", "EmbeddingError", "get_embedding_provider"]
