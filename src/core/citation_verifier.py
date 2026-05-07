"""Lightweight citation verification heuristics."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence


class CitationVerifier:
    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {t for t in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(t) > 2}

    def score_citation(
        self,
        response_text: str,
        citation: Dict[str, Any],
        documents: Sequence[Dict[str, Any]],
    ) -> float:
        chunk_id = str(citation.get("chunk_id", ""))
        doc = next((d for d in documents if str(d.get("id")) == chunk_id), None)
        if not doc:
            return 0.0
        response_terms = self._tokenize(response_text)
        doc_terms = self._tokenize(str(doc.get("text", "")))
        if not response_terms:
            return 0.0
        overlap = len(response_terms & doc_terms) / max(len(response_terms), 1)
        return max(0.0, min(1.0, 0.25 + overlap * 0.75))

    def verify(
        self,
        response_text: str,
        citations: Sequence[Dict[str, Any]],
        documents: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        for citation in citations:
            score = self.score_citation(response_text, citation, documents)
            verdict = "supported" if score >= 0.55 else "weak_support"
            if not citation.get("resolved"):
                verdict = "unresolved"
            output.append({**citation, "verification_score": score, "verification": verdict})
        return output
