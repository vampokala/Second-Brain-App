"""Structured metadata attached to each chunk during vault ingest."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ChunkMeta:
    source: str
    relpath: str
    section: str
    type: str
    title: str
    heading: str | None
    chunk_index: int
    tags: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "relpath": self.relpath,
            "section": self.section,
            "type": self.type,
            "title": self.title,
            "heading": self.heading,
            "chunk_index": self.chunk_index,
            "tags": list(self.tags),
        }

    @classmethod
    def from_mapping(cls, m: Mapping[str, Any], *, default_relpath: str = "") -> "ChunkMeta":
        tags = m.get("tags") or []
        if not isinstance(tags, (list, tuple)):
            tags = []
        return cls(
            source=str(m.get("source") or ""),
            relpath=str(m.get("relpath") or default_relpath),
            section=str(m.get("section") or ""),
            type=str(m.get("type") or m.get("doc_type") or ""),
            title=str(m.get("title") or ""),
            heading=m.get("heading") if m.get("heading") is not None else None,
            chunk_index=int(m.get("chunk_index") or 0),
            tags=tuple(str(t) for t in tags),
        )
