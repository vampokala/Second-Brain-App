"""NLI-based per-response truthfulness scoring.

Uses cross-encoder/nli-deberta-v3-small (≈140 MB, CPU-friendly) to measure
whether response sentences are entailed by the retrieved source chunks.
Labels for that model: contradiction=0, entailment=1, neutral=2.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence


@dataclass
class TruthfulnessResult:
    nli_faithfulness: float
    citation_groundedness: float
    uncited_claims: int
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "nli_faithfulness": self.nli_faithfulness,
            "citation_groundedness": self.citation_groundedness,
            "uncited_claims": self.uncited_claims,
            "score": self.score,
        }


_CITATION_RE = re.compile(r"\[(?:Doc|doc|Chunk|chunk)[^\]]*\]")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _split_claims(text: str) -> List[str]:
    """Return sentences of at least 4 words."""
    return [s.strip() for s in _SENTENCE_SPLIT.split(text.strip()) if len(s.split()) >= 4]


class TruthfulnessScorer:
    """Lazy-loading NLI scorer. One instance per process is sufficient."""

    _model: Any = None
    _model_name: str = "cross-encoder/nli-deberta-v3-small"
    ENTAILMENT_IDX: int = 1  # contradiction=0, entailment=1, neutral=2

    @classmethod
    def _get_model(cls) -> Any:
        if cls._model is None:
            from sentence_transformers import CrossEncoder  # type: ignore[import-untyped]

            cls._model = CrossEncoder(cls._model_name)
        return cls._model

    def nli_faithfulness(self, response: str, source_chunks: Sequence[str]) -> float:
        """Fraction of response sentences entailed by at least one source chunk."""
        if not response.strip() or not source_chunks:
            return 0.0
        claims = _split_claims(response)
        if not claims:
            return 1.0

        nonempty_sources = [s for s in source_chunks if (s or "").strip()]
        if not nonempty_sources:
            return 0.0

        model = self._get_model()
        import numpy as np
        from scipy.special import softmax  # type: ignore[import-untyped]

        entailed = 0
        for claim in claims:
            best = 0.0
            pairs = [(src[:512], claim[:256]) for src in nonempty_sources]
            raw = model.predict(pairs)
            if raw.ndim == 1:
                raw = raw.reshape(1, -1)
            probs = softmax(raw, axis=1)
            best = float(np.max(probs[:, self.ENTAILMENT_IDX]))
            if best >= 0.5:
                entailed += 1
        return entailed / len(claims)

    @staticmethod
    def _citation_groundedness(citations: List[Dict[str, Any]]) -> float:
        if not citations:
            return 0.0
        scores = [float(c.get("verification_score", 0.0)) for c in citations]
        return sum(scores) / len(scores)

    @staticmethod
    def _count_uncited_claims(response: str) -> int:
        claims = _split_claims(response)
        if not claims:
            return 0
        uncited = sum(1 for claim in claims if not _CITATION_RE.search(claim))
        return uncited

    def score(
        self,
        response: str,
        source_chunks: Sequence[str],
        citations: List[Dict[str, Any]],
    ) -> TruthfulnessResult:
        nli = self.nli_faithfulness(response, source_chunks)
        groundedness = self._citation_groundedness(citations)
        uncited = self._count_uncited_claims(response)
        # 60% NLI faithfulness, 40% citation groundedness
        aggregate = round(0.6 * nli + 0.4 * groundedness, 3)
        return TruthfulnessResult(
            nli_faithfulness=round(nli, 3),
            citation_groundedness=round(groundedness, 3),
            uncited_claims=uncited,
            score=aggregate,
        )
