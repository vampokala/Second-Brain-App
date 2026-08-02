"""Pluggable source-connector abstraction.

Each connector fetches records from an external system (GitHub, JIRA,
Confluence, …), normalises them to a :class:`SourceItem`, and the sync
orchestrator writes them through the existing ``IngestPipeline.ingest_text``
so retrieval, embedding, and citations all work unchanged.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass(slots=True)
class SourceItem:
    """A single normalised record ready to be ingested as a markdown file."""

    external_id: str
    title: str
    body_markdown: str
    url: str
    updated_at: str  # ISO-8601; used to advance the incremental cursor
    author: str | None = None
    tags: list[str] = field(default_factory=list)

    def relpath(self, source_type: str, resource_id: str) -> str:
        """Stable vault path so re-syncs upsert the same file."""
        safe_resource = _slug(resource_id)
        safe_id = _slug(self.external_id)
        return f"raw/connectors/{source_type}/{safe_resource}/{safe_id}.md"

    def to_markdown(self, source_type: str) -> str:
        """Frontmatter + body. Frontmatter feeds metadata/citation provenance."""
        tags = ", ".join(self.tags) if self.tags else ""
        lines = [
            "---",
            f'title: "{_escape(self.title)}"',
            f"source: {source_type}",
            f"external_id: {self.external_id}",
            f"source_url: {self.url}",
            f"updated_at: {self.updated_at}",
        ]
        if self.author:
            lines.append(f'author: "{_escape(self.author)}"')
        if tags:
            lines.append(f'tags: "{tags}"')
        lines += ["---", "", f"# {self.title}", "", self.body_markdown.strip(), ""]
        return "\n".join(lines)


class ConnectorError(RuntimeError):
    """Raised when a connector cannot reach or authenticate to its source."""


class SourceConnector(ABC):
    """Base class for all external source connectors."""

    source_type: ClassVar[str]

    def __init__(self, resource_id: str, config: dict, token: str | None = None) -> None:
        self.resource_id = resource_id
        self.config = config or {}
        self.token = token

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Return ``(ok, message)`` after a lightweight auth/reachability check."""

    @abstractmethod
    def fetch(self, cursor: dict | None) -> AsyncIterator[SourceItem]:
        """Yield items updated since ``cursor`` (an async generator).

        Implementations should yield in ascending ``updated_at`` order so the
        orchestrator's max-timestamp cursor advances correctly.
        """


def _slug(value: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", value, flags=re.UNICODE).strip("_")[:96] or "item"


def _escape(value: str) -> str:
    return value.replace('"', "'").replace("\n", " ").strip()
