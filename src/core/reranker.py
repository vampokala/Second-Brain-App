"""Cross-encoder reranking for hybrid retrieval results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Sequence, Tuple, cast

from sentence_transformers import CrossEncoder
from src.core.retrieval_result import RetrievalResult


@dataclass
class RankedResult:
    """Retrieval chunk with cross-encoder score and final rerank position."""

    result: RetrievalResult
    cross_encoder_score: float
    rerank_position: int


class CrossEncoderReranker:
    """Batch cross-encoder scoring and top-k reranking with optional score threshold."""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        batch_size: int = 32,
        score_threshold: float = 0.1,
    ) -> None:
        self.model_name = model_name
        self.batch_size = batch_size
        self.score_threshold = score_threshold
        self._model: CrossEncoder | None = None

    @property
    def model(self) -> CrossEncoder:
        if self._model is None:
            self._model = CrossEncoder(self.model_name)
        return self._model

    def batch_score(self, pairs: List[Tuple[str, str]]) -> List[float]:
        """Score query-document pairs in batches."""
        if not pairs:
            return []
        scores: List[float] = []
        for start in range(0, len(pairs), self.batch_size):
            batch = pairs[start : start + self.batch_size]
            raw = self.model.predict(cast(Any, batch))
            # predict may return ndarray or list of floats
            for s in raw:  # type: ignore[union-attr]
                scores.append(float(s))
        return scores

    def rerank(
        self,
        query: str,
        documents: Sequence[RetrievalResult],
        top_k: int,
    ) -> List[RankedResult]:
        """Rerank retrieval hits by cross-encoder relevance; filter by score_threshold."""
        if not documents:
            return []

        pairs: List[Tuple[str, str]] = [(query, d.text) for d in documents]
        ce_scores = self.batch_score(pairs)

        ranked: List[Tuple[RetrievalResult, float]] = [
            (doc, score) for doc, score in zip(documents, ce_scores) if score >= self.score_threshold
        ]
        if not ranked:
            # keep best-effort: if everything filtered, take top by raw CE anyway
            ranked = list(zip(documents, ce_scores))

        ranked.sort(key=lambda x: x[1], reverse=True)
        ranked = ranked[:top_k]

        return [
            RankedResult(result=doc, cross_encoder_score=score, rerank_position=i)
            for i, (doc, score) in enumerate(ranked)
        ]
