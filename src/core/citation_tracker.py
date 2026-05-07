"""Structured citation mapping utilities."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

_DOC_RE = re.compile(r"\[Doc\s+([^\]]+)\]", re.IGNORECASE)


class CitationTracker:
    def extract_raw_ids(self, text: str) -> List[str]:
        seen: set[str] = set()
        ordered: List[str] = []
        for match in _DOC_RE.finditer(text or ""):
            raw = match.group(1).strip()
            if raw and raw not in seen:
                seen.add(raw)
                ordered.append(raw)
        return ordered

    def build_index_lookup(self, documents: Sequence[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        lookup: Dict[int, Dict[str, Any]] = {}
        for i, doc in enumerate(documents, start=1):
            lookup[i] = doc
        return lookup

    def map_citations(self, response_text: str, documents: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
        known = {str(d.get("id")): d for d in documents}
        by_index = self.build_index_lookup(documents)
        mapped: List[Dict[str, Any]] = []
        for raw_id in self.extract_raw_ids(response_text):
            doc = known.get(raw_id)
            resolved = doc is not None
            chunk_id = raw_id
            if not resolved and raw_id.isdigit():
                indexed_doc = by_index.get(int(raw_id))
                if indexed_doc is not None:
                    doc = indexed_doc
                    chunk_id = str(indexed_doc.get("id"))
                    resolved = True
            metadata = (doc or {}).get("metadata") or {}
            mapped.append(
                {
                    "raw_id": raw_id,
                    "chunk_id": chunk_id,
                    "resolved": resolved,
                    "title": metadata.get("title") or (doc or {}).get("title"),
                    "source": metadata.get("source") or metadata.get("file_type"),
                }
            )
        return mapped
