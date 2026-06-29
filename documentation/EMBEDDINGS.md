# Embeddings

Status: **Accepted** (2026-06-29). See `DECISIONS.md` DEC-020.

## Summary

Knowledge-base semantic search uses **local** embeddings — `BAAI/bge-small-en-v1.5` (384 dimensions) via `fastembed` (ONNX runtime, no PyTorch, no API key, no per-call cost). Claude/Anthropic handles reasoning and response generation only; it does not produce embeddings.

## Architecture

All KB indexing and retrieval talk only to the `EmbeddingProvider` interface — never to a concrete model. Providers are swappable by config.

```
app/ai/embeddings/
├── base.py        EmbeddingProvider (ABC) + EmbeddingError
├── local_bge.py   LocalBGEProvider (default) — bge-small via fastembed
└── __init__.py    get_embedding_provider() factory (config-driven, cached)
```

- `EmbeddingProvider.embed_documents(texts)` — embed KB entries for storage.
- `EmbeddingProvider.embed_query(text)` — embed an incoming question for search (bge query prefix applied).
- `EmbeddingProvider.dimension` — must match the `kb_entries.embedding` column (`vector(384)`).

Selected via `EMBEDDING_PROVIDER` (default `local_bge`) and `EMBEDDING_MODEL` in config. The provider instance is cached (`lru_cache`) so the model loads once per process. Model loads lazily on first use, with retry/backoff on load (first use downloads the model); inference is local and not retried.

## Adding another provider (e.g. Voyage, OpenAI)

1. Create a class implementing `EmbeddingProvider` in `app/ai/embeddings/`.
2. Register it in the `_PROVIDERS` map in `__init__.py`.
3. Add any needed key to config and set `EMBEDDING_PROVIDER=<name>`.
4. If the new model's dimension differs from 384, add a migration altering `kb_entries.embedding`.

No knowledge-base code changes.

## Trade-offs / limitations of the local approach

- **Quality**: bge-small is good but below top hosted models (Voyage, OpenAI large). Acceptable for MVP; revisit if pilot retrieval is weak.
- **Latency**: CPU inference adds modest latency vs. a hosted API (which has network latency instead).
- **First-use download**: the model downloads on first use (cached afterward). Tests that load the model are skipped in CI to keep it fast.
- **Dimension coupling**: the DB column is `vector(384)`; switching to a different-dimension model requires a migration and re-embedding existing entries.
