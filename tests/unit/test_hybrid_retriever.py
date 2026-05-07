from unittest.mock import MagicMock

from src.core.bm25_search import BM25Search
from src.core.hybrid_retriever import FusionConfig, HybridRetriever, reciprocal_rank_fusion
from src.core.vector_search import VectorSearch


def test_reciprocal_rank_fusion_prefers_consensus_top():
    bm25 = ["a", "b", "c"]
    vec = ["b", "c", "a"]
    fused = reciprocal_rank_fusion([bm25, vec], k_rrf=60)
    assert fused[0][0] == "b"


def test_reciprocal_rank_fusion_stable_tiebreak():
    fused = reciprocal_rank_fusion([["x", "y"], ["y", "x"]], k_rrf=1)
    assert fused[0][1] == fused[1][1]
    assert fused[0][0] < fused[1][0]


def test_hybrid_retriever_rrf_not_concat_order():
    bm25 = MagicMock(spec=BM25Search)
    bm25.search.return_value = [
        {"id": "doc_a", "text": "ta", "metadata": {}, "score": 99.0},
        {"id": "doc_b", "text": "tb", "metadata": {}, "score": 1.0},
    ]
    vec = MagicMock(spec=VectorSearch)
    vec.search.return_value = [
        {"id": "doc_b", "text": "tb", "metadata": {}, "distance": 0.1},
        {"id": "doc_c", "text": "tc", "metadata": {}, "distance": 0.2},
    ]

    h = HybridRetriever(bm25, vec, enable_cache=False)
    out = h.retrieve("bm25 q", "vec q", k=3)
    ids = [r.id for r in out]
    assert ids[0] == "doc_b"
    assert set(ids) == {"doc_a", "doc_b", "doc_c"}


def test_hybrid_cache_returns_copy_and_skips_second_search():
    bm25 = MagicMock(spec=BM25Search)
    bm25.search.return_value = [{"id": "a", "text": "t", "metadata": {}, "score": 1.0}]
    vec = MagicMock(spec=VectorSearch)
    vec.search.return_value = [{"id": "a", "text": "t", "metadata": {}, "distance": 0.5}]

    h = HybridRetriever(
        bm25,
        vec,
        enable_cache=True,
        fusion_config=FusionConfig(cache_max_entries=4),
    )
    r1 = h.retrieve("q1", "q2", k=1)
    h.retrieve("q1", "q2", k=1)
    assert bm25.search.call_count == 1
    r1[0].text = "mutated"
    r3 = h.retrieve("q1", "q2", k=1)
    assert r3[0].text == "t"
