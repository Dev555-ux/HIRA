"""Tests for the embedding provider abstraction and the local BGE provider.

The real model-load test downloads the model, so it is skipped in CI (CI env
var) to keep the pipeline fast; it still runs locally. The factory and dimension
contract are tested without loading the model.
"""

import os

import pytest

from app.ai.embeddings import EmbeddingError, get_embedding_provider
from app.ai.embeddings.base import EmbeddingProvider
from app.ai.embeddings.local_bge import BGE_SMALL_DIMENSION, LocalBGEProvider


def test_factory_returns_local_provider_by_default():
    provider = get_embedding_provider("local_bge")
    assert isinstance(provider, LocalBGEProvider)
    assert isinstance(provider, EmbeddingProvider)


def test_factory_unknown_provider_raises():
    with pytest.raises(EmbeddingError):
        get_embedding_provider("does-not-exist")


def test_local_provider_reports_correct_dimension():
    # No model load needed — dimension is a fixed property.
    assert LocalBGEProvider().dimension == BGE_SMALL_DIMENSION == 384


@pytest.mark.skipif(bool(os.environ.get("CI")), reason="downloads the embedding model")
def test_local_provider_embeds_query_and_documents():
    provider = LocalBGEProvider()
    doc_vecs = provider.embed_documents(["We are open 9am to 5pm on weekdays."])
    query_vec = provider.embed_query("what are your opening hours?")

    assert len(doc_vecs) == 1
    assert len(doc_vecs[0]) == 384
    assert len(query_vec) == 384
    assert all(isinstance(x, float) for x in query_vec)
