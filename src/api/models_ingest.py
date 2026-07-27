"""Pydantic models for manual vault ingest API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl


class IngestTextBody(BaseModel):
    text: str = Field(..., min_length=1)
    """Relative path under vault (e.g. raw/notes/pasted.md)."""

    relpath: str = Field(..., min_length=1)


class IngestUrlBody(BaseModel):
    url: HttpUrl
    """Optional relative markdown path to write (default derived from URL)."""

    relpath: str | None = None


class IngestItemResult(BaseModel):
    path: str
    status: Literal["queued", "processing", "ingested", "failed", "skipped", "cancelled"]
    chunk_count: int = 0
    error: str | None = None


class IngestResponse(BaseModel):
    results: list[IngestItemResult]


class IngestScanSummary(BaseModel):
    total: int = 0
    ingested: int = 0
    skipped: int = 0
    failed: int = 0
    cancelled: int = 0


class IngestScanResponse(BaseModel):
    results: list[IngestItemResult]
    summary: IngestScanSummary


class IngestScanStartResponse(BaseModel):
    status: Literal["started"]
    detail: str | None = None
    selected: int | None = None


class IngestScanFile(BaseModel):
    path: str
    change: Literal["new", "changed"]
    size: int = 0
    mtime_ms: int = 0


class IngestScanPreviewSummary(BaseModel):
    total_scanned: int = 0
    new: int = 0
    changed: int = 0
    unchanged: int = 0


class IngestScanPreviewResponse(BaseModel):
    files: list[IngestScanFile]
    summary: IngestScanPreviewSummary


class IngestPathsBody(BaseModel):
    paths: list[str] = Field(..., min_length=1, max_length=5000)


class ReindexResponse(BaseModel):
    status: Literal["started", "ok", "failed"]
    detail: str | None = None


class IngestEventPayload(BaseModel):
    file_path: str
    event_type: str
    status: str
    details: dict[str, Any] | None = None
    phase: str | None = None
    message: str | None = None
    relative_path: str | None = None
    current: int | None = None
    total: int | None = None
