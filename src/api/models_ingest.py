"""Pydantic models for manual vault ingest API."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class IngestTextBody(BaseModel):
    text: str = Field(..., min_length=1)
    """Relative path under vault (e.g. raw/notes/pasted.md)."""

    relpath: str = Field(..., min_length=1)


class IngestUrlBody(BaseModel):
    url: HttpUrl
    """Optional relative markdown path to write (default derived from URL)."""

    relpath: Optional[str] = None


class IngestItemResult(BaseModel):
    path: str
    status: Literal["queued", "processing", "ingested", "failed"]
    chunk_count: int = 0
    error: Optional[str] = None


class IngestResponse(BaseModel):
    results: list[IngestItemResult]


class ReindexResponse(BaseModel):
    status: Literal["started", "ok", "failed"]
    detail: Optional[str] = None


class IngestEventPayload(BaseModel):
    file_path: str
    event_type: str
    status: str
    details: Optional[dict[str, Any]] = None
