"""Post-process LLM answers: citations, formatting, light quality heuristics."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

_DOC_CITATION_RE = re.compile(r"\[Doc\s+([^\]]+)\]", re.IGNORECASE)
_BRACKET_RE = re.compile(r"\[([^\]]+)\]")


class ResponseProcessor:
    """Citation extraction and simple quality scoring."""

    @staticmethod
    def extract_citations(response: str, documents: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find [Doc id] citations and map to known chunk ids when possible."""
        known_ids = {str(d.get("id")) for d in documents}
        found: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for m in _DOC_CITATION_RE.finditer(response or ""):
            raw_id = m.group(1).strip()
            if raw_id in seen:
                continue
            seen.add(raw_id)
            found.append(
                {
                    "id": raw_id,
                    "resolved": raw_id in known_ids,
                    "span": m.group(0),
                }
            )
        # Secondary: bare bracket ids that match a chunk id
        for m in _BRACKET_RE.finditer(response or ""):
            inner = m.group(1).strip()
            if inner.lower().startswith("doc "):
                continue
            if inner in known_ids and inner not in seen:
                seen.add(inner)
                found.append({"id": inner, "resolved": True, "span": m.group(0)})
        return found

    @staticmethod
    def format_response(response: str) -> str:
        text = (response or "").strip()
        text = re.sub(r"\r\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    @staticmethod
    def score_quality(response: str, query: str) -> float:
        """Heuristic 0..1: length, citation count, token overlap with query."""
        text = (response or "").strip()
        if len(text) < 20:
            return 0.0
        q_terms = {w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2}
        r_terms = {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2}
        overlap = (len(q_terms & r_terms) / max(len(q_terms), 1)) if q_terms else 0.3
        cite_bonus = min(0.35, 0.07 * len(_DOC_CITATION_RE.findall(text)))
        length_score = min(0.35, len(text) / 800.0)
        return max(0.0, min(1.0, 0.25 + overlap * 0.45 + cite_bonus + length_score))
