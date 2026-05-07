"""Standardized hybrid retrieval payloads for downstream LLM / reranking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RetrievalResult:
    """Single chunk after fusion with traceability to sparse / dense legs."""

    id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    fusion_score: float = 0.0
    bm25_rank: Optional[int] = None
    vector_rank: Optional[int] = None
    bm25_score: Optional[float] = None
    vector_similarity: Optional[float] = None
    sources: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_legacy_dict(self) -> Dict[str, Any]:
        """Backward-compatible shape for callers expecting id/text/source/score."""
        if len(self.sources) > 1:
            primary = "hybrid"
        elif self.sources:
            primary = self.sources[0]
        else:
            primary = "hybrid"
        return {
            "id": self.id,
            "text": self.text,
            "metadata": self.metadata,
            "source": primary,
            "sources": self.sources,
            "score": self.fusion_score,
            "bm25_rank": self.bm25_rank,
            "vector_rank": self.vector_rank,
            "bm25_score": self.bm25_score,
            "vector_similarity": self.vector_similarity,
            "confidence": self.confidence,
        }
