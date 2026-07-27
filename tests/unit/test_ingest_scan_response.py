"""Ingest scan response model shape."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from src.api.models_ingest import (
    IngestItemResult,
    IngestPathsBody,
    IngestScanFile,
    IngestScanPreviewResponse,
    IngestScanPreviewSummary,
    IngestScanResponse,
    IngestScanStartResponse,
    IngestScanSummary,
)


def test_ingest_scan_response_shape() -> None:
    body = IngestScanResponse(
        results=[
            IngestItemResult(path="raw/a.md", status="ingested", chunk_count=2),
            IngestItemResult(path="raw/b.md", status="skipped", chunk_count=0),
        ],
        summary=IngestScanSummary(total=2, ingested=1, skipped=1, failed=0, cancelled=0),
    )
    dumped = body.model_dump()
    assert dumped["summary"]["total"] == 2
    assert dumped["summary"]["ingested"] == 1
    assert len(dumped["results"]) == 2


def test_ingest_scan_preview_response_shape() -> None:
    body = IngestScanPreviewResponse(
        files=[
            IngestScanFile(path="raw/a.md", change="new", size=1, mtime_ms=1),
            IngestScanFile(path="raw/b.md", change="changed", size=2, mtime_ms=2),
        ],
        summary=IngestScanPreviewSummary(total_scanned=3, new=1, changed=1, unchanged=1),
    )
    dumped = body.model_dump()
    assert dumped["summary"]["new"] == 1
    assert dumped["files"][0]["change"] == "new"
    assert len(dumped["files"]) == 2


def test_ingest_scan_start_response() -> None:
    started = IngestScanStartResponse(status="started", detail="ok", selected=3)
    assert started.status == "started"
    assert started.selected == 3


def test_ingest_paths_body_requires_paths() -> None:
    with pytest.raises(ValidationError):
        IngestPathsBody(paths=[])
    body = IngestPathsBody(paths=["raw/a.md"])
    assert body.paths == ["raw/a.md"]
