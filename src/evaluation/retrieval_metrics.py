"""Information-retrieval metrics (pure Python; no numpy required)."""

from __future__ import annotations

import math
from typing import Dict, Iterable, Mapping, Sequence, Set


def precision_at_k(ranked_ids: Sequence[str], relevant: Set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top = list(ranked_ids)[:k]
    if not top:
        return 0.0
    hits = sum(1 for d in top if d in relevant)
    return hits / min(k, len(top))


def recall_at_k(ranked_ids: Sequence[str], relevant: Set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top = set(list(ranked_ids)[:k])
    hits = len(top & relevant)
    return hits / len(relevant)


def f1_at_k(ranked_ids: Sequence[str], relevant: Set[str], k: int) -> float:
    p = precision_at_k(ranked_ids, relevant, k)
    r = recall_at_k(ranked_ids, relevant, k)
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)


def hit_rate_at_k(ranked_ids: Sequence[str], relevant: Set[str], k: int) -> float:
    top = list(ranked_ids)[:k]
    return 1.0 if any(d in relevant for d in top) else 0.0


def reciprocal_rank(ranked_ids: Sequence[str], relevant: Set[str]) -> float:
    for i, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant:
            return 1.0 / i
    return 0.0


def mean_reciprocal_rank(queries_results: Mapping[str, Sequence[str]], qrels: Mapping[str, Set[str]]) -> float:
    if not qrels:
        return 0.0
    total = 0.0
    for q, rel in qrels.items():
        ranked = queries_results.get(q, [])
        total += reciprocal_rank(ranked, rel)
    return total / len(qrels)


def average_precision(ranked_ids: Sequence[str], relevant: Set[str]) -> float:
    if not relevant:
        return 0.0
    ap = 0.0
    hits = 0
    for i, doc_id in enumerate(ranked_ids, start=1):
        if doc_id in relevant:
            hits += 1
            ap += hits / i
    return ap / len(relevant)


def mean_average_precision(queries_results: Mapping[str, Sequence[str]], qrels: Mapping[str, Set[str]]) -> float:
    if not qrels:
        return 0.0
    return sum(average_precision(queries_results[q], rel) for q, rel in qrels.items()) / len(qrels)


def _dcg(relevances: Sequence[float]) -> float:
    return sum(rel / math.log2(i + 2) for i, rel in enumerate(relevances))


def ndcg_at_k(
    ranked_ids: Sequence[str],
    graded_relevance: Mapping[str, float],
    k: int,
) -> float:
    """NDCG@k with graded gains in ``graded_relevance`` (binary: 0/1 still works)."""
    if k <= 0:
        return 0.0
    gains = [float(graded_relevance.get(d, 0.0)) for d in list(ranked_ids)[:k]]
    ideal = sorted((graded_relevance.get(d, 0.0) for d in graded_relevance), reverse=True)[:k]
    while len(ideal) < k:
        ideal.append(0.0)
    idcg = _dcg(ideal[:k])
    if idcg == 0:
        return 0.0
    return _dcg(gains) / idcg


def coverage(queries_results: Mapping[str, Sequence[str]], corpus_ids: Set[str], k: int) -> float:
    """Fraction of corpus appearing in top-k across all query result lists."""
    if not corpus_ids:
        return 0.0
    seen: Set[str] = set()
    for ranked in queries_results.values():
        seen.update(list(ranked)[:k])
    return len(seen & corpus_ids) / len(corpus_ids)


def evaluate_all(
    queries_results: Mapping[str, Sequence[str]],
    qrels: Mapping[str, Set[str]],
    k_values: Iterable[int] = (1, 3, 5, 10),
) -> Dict[str, float]:
    """Aggregate common metrics over a query suite (binary qrels)."""
    out: Dict[str, float] = {}
    ks = list(k_values)
    for k in ks:
        precs = [precision_at_k(queries_results[q], rel, k) for q, rel in qrels.items()]
        recalls = [recall_at_k(queries_results[q], rel, k) for q, rel in qrels.items()]
        f1s = [f1_at_k(queries_results[q], rel, k) for q, rel in qrels.items()]
        hits = [hit_rate_at_k(queries_results[q], rel, k) for q, rel in qrels.items()]
        out[f"precision@{k}"] = sum(precs) / len(precs) if precs else 0.0
        out[f"recall@{k}"] = sum(recalls) / len(recalls) if recalls else 0.0
        out[f"f1@{k}"] = sum(f1s) / len(f1s) if f1s else 0.0
        out[f"hit_rate@{k}"] = sum(hits) / len(hits) if hits else 0.0
    out["mrr"] = mean_reciprocal_rank(queries_results, qrels)
    out["map"] = mean_average_precision(queries_results, qrels)
    return out
