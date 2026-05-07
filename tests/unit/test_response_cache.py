"""Response cache key semantics."""

from src.core.response_cache import cache_key


def test_cache_key_differs_for_stream_vs_sync():
    base = dict(
        query="what is RAG",
        model="m",
        top_k=5,
        provider="ollama",
        use_rerank=True,
        reranker_model="cross",
        corpus_fingerprint="fp",
    )
    k_sync = cache_key(**base, response_mode="sync")
    k_stream = cache_key(**base, response_mode="stream")
    assert k_sync != k_stream


def test_cache_key_default_is_sync_matches_explicit():
    k1 = cache_key("q", "m", 3)
    k2 = cache_key("q", "m", 3, response_mode="sync")
    assert k1 == k2
