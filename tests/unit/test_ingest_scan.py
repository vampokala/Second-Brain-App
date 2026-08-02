"""Unit tests for vault path filters and scan summary (no heavy deps)."""

from __future__ import annotations

from pathlib import Path

from src.api.models_ingest import IngestItemResult, IngestScanSummary
from src.core.ingest_paths import should_skip_path


def _summarize_results(results: list[IngestItemResult]) -> IngestScanSummary:
    return IngestScanSummary(
        total=len(results),
        ingested=sum(1 for r in results if r.status == "ingested"),
        skipped=sum(1 for r in results if r.status == "skipped"),
        failed=sum(1 for r in results if r.status == "failed"),
        cancelled=sum(1 for r in results if r.status == "cancelled"),
    )


def test_should_skip_path_junk_names(tmp_path: Path) -> None:
    vault = tmp_path
    assert should_skip_path(vault / "raw" / ".DS_Store", vault) is True
    assert should_skip_path(vault / "raw" / "note.tmp", vault) is True
    assert should_skip_path(vault / "raw" / "~$draft.docx", vault) is True


def test_should_skip_path_hidden_dirs(tmp_path: Path) -> None:
    vault = tmp_path
    assert should_skip_path(vault / "raw" / ".git" / "config", vault) is True
    assert should_skip_path(vault / "raw" / "node_modules" / "x.js", vault) is True
    assert should_skip_path(vault / "raw" / "ok.md", vault) is False


def test_summarize_results_counts_statuses() -> None:
    results = [
        IngestItemResult(path="a", status="ingested", chunk_count=1),
        IngestItemResult(path="b", status="skipped", chunk_count=0),
        IngestItemResult(path="c", status="failed", chunk_count=0, error="x"),
        IngestItemResult(path="d", status="cancelled", chunk_count=0),
    ]
    summary = _summarize_results(results)
    assert summary.total == 4
    assert summary.ingested == 1
    assert summary.skipped == 1
    assert summary.failed == 1
    assert summary.cancelled == 1
