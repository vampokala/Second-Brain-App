"""BM25 search facade over BM25Index (spec: bm25_search.py)."""

from __future__ import annotations

import html
import re
from typing import Dict, List

from src.core.bm25_index import BM25Index


class BM25Search:
    def __init__(self, index: BM25Index):
        self._index = index

    def search(self, query: str, k: int = 50) -> List[Dict]:
        return self._index.score(query, top_k=k)

    def score_documents(self, query: str) -> Dict[str, float]:
        rows = self._index.score(query, top_k=None)
        return {r["id"]: float(r["score"]) for r in rows}

    @staticmethod
    def highlight_terms(text: str, query_terms: List[str], max_spans: int = 20) -> str:
        """Wrap query term hits in << >> markers (plain text, safe)."""
        if not text or not query_terms:
            return html.escape(text) if text else ""

        terms = sorted({t.lower() for t in query_terms if len(t) > 0}, key=len, reverse=True)
        if not terms:
            return html.escape(text)

        pattern = "|".join(re.escape(t) for t in terms)
        rx = re.compile(f"({pattern})", re.IGNORECASE)
        out: List[str] = []
        last = 0
        spans = 0
        for m in rx.finditer(text):
            if spans >= max_spans:
                break
            out.append(html.escape(text[last : m.start()]))
            out.append("<<")
            out.append(html.escape(m.group(0)))
            out.append(">>")
            last = m.end()
            spans += 1
        out.append(html.escape(text[last:]))
        return "".join(out)
