"""Hybrid BM25 + dense retrieval with reciprocal rank fusion (RRF)."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.core.bm25_search import BM25Search
from src.core.retrieval_result import RetrievalResult
from src.core.vector_search import VectorSearch


@dataclass
class FusionConfig:
    k_rrf: int = 60
    candidate_k_bm25: int = 50
    candidate_k_vector: int = 50
    parallel: bool = True
    cache_max_entries: int = 128


class _LRUCache:
    def __init__(self, max_entries: int) -> None:
        self._max = max(0, max_entries)
        self._store: OrderedDict[str, List[RetrievalResult]] = OrderedDict()

    def get(self, key: str) -> Optional[List[RetrievalResult]]:
        if self._max == 0:
            return None
        if key not in self._store:
            return None
        self._store.move_to_end(key)
        # Return shallow copies so callers cannot mutate cache entries
        return [RetrievalResult(**r.__dict__) for r in self._store[key]]

    def set(self, key: str, value: List[RetrievalResult]) -> None:
        if self._max == 0:
            return
        self._store[key] = [RetrievalResult(**r.__dict__) for r in value]
        self._store.move_to_end(key)
        while len(self._store) > self._max:
            self._store.popitem(last=False)


def reciprocal_rank_fusion(
    ranked_lists: List[List[str]],
    k_rrf: int = 60,
    weights: Optional[List[float]] = None,
) -> List[Tuple[str, float]]:
    """
    Standard RRF: score(d) = sum_i 1 / (k_rrf + rank_i(d)).
    Missing from a list means that list does not contribute for that document.
    """
    scores: Dict[str, float] = {}
    for idx, ids in enumerate(ranked_lists):
        weight = 1.0
        if weights and idx < len(weights):
            weight = weights[idx]
        for rank, doc_id in enumerate(ids, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + weight * (1.0 / (k_rrf + rank))
    return sorted(scores.items(), key=lambda x: (-x[1], x[0]))


class HybridRetriever:
    """Combines BM25Search and VectorSearch; ranks with RRF."""

    def __init__(
        self,
        bm25_search: BM25Search,
        vector_search: VectorSearch,
        *,
        fusion_weights: Optional[Dict[str, float]] = None,
        fusion_config: Optional[FusionConfig] = None,
        enable_cache: bool = True,
    ) -> None:
        self.bm25 = bm25_search
        self.vector = vector_search
        self.fusion_weights = fusion_weights or {"vector": 0.6, "bm25": 0.4}
        self.config = fusion_config or FusionConfig()
        self._cache = _LRUCache(self.config.cache_max_entries) if enable_cache else _LRUCache(0)

    def reciprocal_rank_fusion(
        self,
        ranked_lists: List[List[str]],
        k_rrf: Optional[int] = None,
    ) -> List[Tuple[str, float]]:
        k = k_rrf if k_rrf is not None else self.config.k_rrf
        weights = [self.fusion_weights.get("bm25", 1.0), self.fusion_weights.get("vector", 1.0)]
        return reciprocal_rank_fusion(ranked_lists, k_rrf=k, weights=weights)

    @staticmethod
    def _cache_key_parts(
        bm25_query: str,
        vector_query: str,
        k: int,
        k_rrf: int,
        ck_bm25: int,
        ck_vec: int,
        collection: str,
    ) -> str:
        raw = f"{collection}|{k}|{k_rrf}|{ck_bm25}|{ck_vec}|BM25:{bm25_query}|VEC:{vector_query}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _run_bm25(self, bm25_query: str, k: int) -> List[Dict[str, Any]]:
        return self.bm25.search(bm25_query, k=k)

    def _run_vector(self, vector_query: str, k: int, filters: Optional[Dict]) -> List[Dict[str, Any]]:
        return self.vector.search(vector_query, k=k, filters=filters)

    def retrieve(
        self,
        bm25_query: str,
        vector_query: str,
        k: int = 20,
        *,
        filters: Optional[Dict] = None,
        collection_name_for_cache: str = "documents",
    ) -> List[RetrievalResult]:
        cfg = self.config
        ck_b = max(k, cfg.candidate_k_bm25)
        ck_v = max(k, cfg.candidate_k_vector)

        cache_key = self._cache_key_parts(
            bm25_query, vector_query, k, cfg.k_rrf, ck_b, ck_v, collection_name_for_cache
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached[:k]

        bm25_hits: List[Dict[str, Any]] = []
        vec_hits: List[Dict[str, Any]] = []

        if cfg.parallel:
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_b = ex.submit(self._run_bm25, bm25_query, ck_b)
                f_v = ex.submit(self._run_vector, vector_query, ck_v, filters)
                bm25_hits = f_b.result()
                vec_hits = f_v.result()
        else:
            bm25_hits = self._run_bm25(bm25_query, ck_b)
            vec_hits = self._run_vector(vector_query, ck_v, filters)

        bm25_ids = [str(h["id"]) for h in bm25_hits]
        vec_ids = [str(h["id"]) for h in vec_hits]

        weights = [self.fusion_weights.get("bm25", 1.0), self.fusion_weights.get("vector", 1.0)]
        fused = reciprocal_rank_fusion([bm25_ids, vec_ids], k_rrf=cfg.k_rrf, weights=weights)

        by_id: Dict[str, Dict[str, Any]] = {}
        for h in bm25_hits:
            by_id[str(h["id"])] = {**h, "_from_bm25": True}
        for h in vec_hits:
            hid = str(h["id"])
            if hid not in by_id:
                by_id[hid] = {**h, "_from_bm25": False}
            else:
                # merge vector-specific fields
                entry = by_id[hid]
                if "distance" in h and "distance" not in entry:
                    entry["distance"] = h["distance"]
                entry["_from_vector"] = True

        bm25_rank: Dict[str, int] = {doc_id: i + 1 for i, doc_id in enumerate(bm25_ids)}
        vec_rank: Dict[str, int] = {doc_id: i + 1 for i, doc_id in enumerate(vec_ids)}

        results: List[RetrievalResult] = []
        for doc_id, fusion_score in fused[:k]:
            row = by_id.get(doc_id, {})
            text = row.get("text") or ""
            meta = row.get("metadata") or {}
            bm25_sc = row.get("score")
            dist = row.get("distance")
            vec_sim = (1.0 - float(dist)) if dist is not None else None

            sources: List[str] = []
            if doc_id in bm25_rank:
                sources.append("bm25")
            if doc_id in vec_rank:
                sources.append("vector")

            br = bm25_rank.get(doc_id)
            vr = vec_rank.get(doc_id)
            confidence = self._confidence(fusion_score, br, vr)

            results.append(
                RetrievalResult(
                    id=doc_id,
                    text=text,
                    metadata=meta if isinstance(meta, dict) else {},
                    fusion_score=fusion_score,
                    bm25_rank=br,
                    vector_rank=vr,
                    bm25_score=float(bm25_sc) if bm25_sc is not None else None,
                    vector_similarity=vec_sim,
                    sources=sources,
                    confidence=confidence,
                )
            )

        self._cache.set(cache_key, results)
        return [RetrievalResult(**r.__dict__) for r in results]

    @staticmethod
    def _confidence(fusion_score: float, bm25_rank: Optional[int], vec_rank: Optional[int]) -> float:
        """Heuristic 0..1 from RRF score and how strong each leg is."""
        parts: List[float] = []
        if bm25_rank is not None:
            parts.append(1.0 / bm25_rank)
        if vec_rank is not None:
            parts.append(1.0 / vec_rank)
        leg = sum(parts) / max(len(parts), 1) if parts else 0.0
        return min(1.0, 0.5 * fusion_score + 0.5 * leg)
